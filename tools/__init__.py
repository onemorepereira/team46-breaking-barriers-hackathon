"""Tools: everything specific to a tool server lives here, one subpackage per server.

- tools/<server>/descriptors.py: static facts (server id, tool names, area-reading tools, dataset fields).
  Pure: no network, no SDK. Analysis may import these.
- tools/<server>/results.py: parsing a server's tool output. Pure; analysis and the UI may import these.
- tools/<server>/client.py (+ auth, login): building the MCP client; used by the agent runtime and harness.
- tools/registry.py: builds every configured MCP client for the agent.
- tools/scripted.py: test fakes for the external boundary (a scripted model and a local tool).
"""
