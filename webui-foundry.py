from azure.identity import ClientSecretCredential, get_bearer_token_provider
import openai

from pydantic import BaseModel, Field

# Simple module-level cache to avoid rebuilding OpenAI clients on every request.
_CLIENT_CACHE = None
_CLIENT_CACHE_KEY = None

class Pipe:
    class Valves(BaseModel):
        TENANT_ID: str = Field(
            default="xxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            description="Azure Tenant ID for authentication.",
        )
        CLIENT_ID: str = Field(
            default="xxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            description="Azure Client ID for authentication.",
        )
        CLIENT_SECRET: str = Field(
            default="xxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            description="Azure Client Secret for authentication.",
        )
        BASE_URL: str = Field(
            default="https://<resource-name>.services.ai.azure.com/api/projects/firstProject/openai",
            description="The base URL to use with the Foundry project.",
        )

    #
    # Place your agents here!
    #
    def pipes(self):
        # Agents to display
        return [
            {"id": "writer-agent", "name": "writer-agent"},
            {"id": "editor-agent", "name": "editor-agent"},
            {"id": "sharepoint-store-1", "name": "sharepoint-store-1"},
        ]

    def __init__(self):
        self.valves = self.Valves()

    def pipe(self, body: dict):

        # STEP 1: Setup (and cache) OpenAI client with Azure AD authentication
        openai_client = get_client(self.valves)

        # END STEP 1

        # STEP 2: Transform the user’s messages into the format the Responses API expects
        all_messages = body.get("messages", [])
        transformed_messsage_array = transform_chat_messages_to_responses_api_format(
            all_messages
        )

        # END STEP 2
        
        # STEP 3: Call the Responses API with the agent reference

        agent_model_name = body.get("model", "") or self.valves.AGENT_NAME
        agent_reference_name = agent_model_name.rsplit(".", 1)[-1]

        result = openai_client.responses.create(
            extra_body={
                "agent": {
                    "name": agent_reference_name,
                    "type": "agent_reference"
                }
            },
            #instructions=transformed_messsage_array["instructions"], #Instructions not supported if using agent_reference
            input=transformed_messsage_array["input"],
            stream=True,
            tool_choice="auto",
        )

        # END STEP 3

        # STEP 4: Stream the output deltas back to the caller
        for event in result:
            if event.type == 'response.output_text.delta':
                yield event.delta


def transform_chat_messages_to_responses_api_format(messages):
    """
    Convert WebUI Chat-Completions history → OpenAI Responses format.

    INPUT EXAMPLE
        [
            {"role": "system",    "content": "You are helpful."},
            {"role": "user",      "content": "Hi!"},
            {"role": "assistant", "content": "Hello 👋"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What’s in this picture?"},
                    {"type": "image_url",
                     "image_url": {"url": "data:image/png;base64,AAA…"}}
                ]
            }
        ]

    OUTPUT EXAMPLE
        {
            "instructions": "You are helpful.",
            "input": [
                {"role": "user",
                 "content": [{"type": "input_text",
                              "text": "Hi!"}]},
                {"role": "assistant",
                 "content": [{"type": "output_text",
                              "text": "Hello 👋"}]},
                {"role": "user",
                 "content": [
                     {"type": "input_text",
                      "text": "What’s in this picture?"},
                     {"type": "input_image",
                      "image_url": "data:image/png;base64,AAA…"}
                 ]}
            ]
        }
    """
    instructions = None
    output = []

    # ── system → instructions ───────────────────────────────────────────────
    if messages and messages[0].get("role") == "system":
        instructions = str(messages[0].get("content", "")).strip()
        messages = messages[1:]

    # ── convert remaining messages ──────────────────────────────────────────
    for msg in messages:
        role = msg.get("role", "user")
        is_assistant = role == "assistant"

        items = msg.get("content", [])
        if not isinstance(items, list):
            items = [items]

        converted = []
        for item in items:
            if item is None:  # guard against nulls
                continue

            # A) structured dict items
            if isinstance(item, dict):
                itype = item.get("type", "text")

                if is_assistant:
                    if itype == "refusal":
                        converted.append(
                            {
                                "type": "refusal",
                                "reason": item.get("reason", "No reason"),
                            }
                        )
                    else:  # output text
                        converted.append(
                            {"type": "output_text", "text": item.get("text", "")}
                        )
                else:  # user
                    if itype == "image_url":
                        url = item.get("image_url", {}).get("url", "")
                        converted.append({"type": "input_image", "image_url": url})
                    else:  # input text
                        converted.append(
                            {"type": "input_text", "text": item.get("text", "")}
                        )
            # B) primitive str / int items
            else:
                text_val = item if isinstance(item, str) else str(item)
                converted.append(
                    {
                        "type": "output_text" if is_assistant else "input_text",
                        "text": text_val,
                    }
                )

        output.append({"role": role, "content": converted})

    return {"instructions": instructions, "input": output}


def get_client(valves: Pipe.Valves):
    global _CLIENT_CACHE, _CLIENT_CACHE_KEY

    base_url = valves.BASE_URL.rstrip("/")
    cache_key = (
        valves.TENANT_ID,
        valves.CLIENT_ID,
        valves.CLIENT_SECRET,
        base_url,
    )

    if _CLIENT_CACHE is not None and _CLIENT_CACHE_KEY == cache_key:
        return _CLIENT_CACHE

    credential = ClientSecretCredential(
        tenant_id=valves.TENANT_ID,
        client_id=valves.CLIENT_ID,
        client_secret=valves.CLIENT_SECRET,
    )

    token_provider = get_bearer_token_provider(
        credential,
        "https://ai.azure.com/.default",
    )

    input_url = f"{base_url}/openai"

    openai_client = openai.OpenAI(
        api_key=token_provider,
        base_url=input_url,
        default_query={"api-version": "2025-11-15-preview"},
    )

    _CLIENT_CACHE = openai_client
    _CLIENT_CACHE_KEY = cache_key

    return openai_client