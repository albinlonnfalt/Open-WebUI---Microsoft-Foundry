# Open WebUI Microsoft Foundry Pipe

This repository contains a pipe function that lets Open WebUI surface agents and workflows hosted in Microsoft Foundry. It is an extremely early version with only the minimum viable functionality, but it demonstrates how to call Foundry agents via the Responses API.

## Setup

- Create a Microsoft Entra app registration and give it the **AI User** RBAC role on the Foundry resource.
- Provide the generated tenant ID, client ID, and client secret as environment variables or configuration fields so the pipe can authenticate to Foundry.
- Set the `BASE_URL` valve to point at your Foundry project's endpoint.

## Registering Agents

Add each agent name you want to expose as a separate entry in the `pipes` method of `Pipe`. Every agent added there will appear as its own model option inside the Open WebUI.

## Usage notes

- The pipe currently only supports the bare-minimum flow (authenticate, transform chat history, call Responses API with agent references). Enhancements such as streaming, richer input types, or retries are not yet implemented.
- Treat this code as a starting point for more advanced agent/workflow integrations with Foundry.

## Limitations
Currently the following functionality is not supported:
- Code interpreter
- Image input
- Tool use not configured in the agent
