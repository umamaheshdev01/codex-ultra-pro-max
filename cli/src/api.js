export async function* streamChat(
  message,
  sessionId,
  projectRoot,
  backendUrl,
  skillName = null,
) {
  const response = await fetch(`${backendUrl}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      project_root: projectRoot,
      skill_name: skillName,
    }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Chat response did not include a readable body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data:")) {
        continue;
      }

      const data = line.slice("data:".length).trim();
      if (!data) {
        continue;
      }

      yield JSON.parse(data);
    }
  }

  buffer += decoder.decode();
  const remaining = buffer.trim();
  if (remaining.startsWith("data:")) {
    yield JSON.parse(remaining.slice("data:".length).trim());
  }
}

export async function checkHealth(backendUrl) {
  try {
    const response = await fetch(`${backendUrl}/health`);
    if (!response.ok) {
      return false;
    }

    const payload = await response.json();
    return payload?.ok === true;
  } catch {
    return false;
  }
}

export async function clearSession(sessionId, backendUrl) {
  const response = await fetch(`${backendUrl}/clear`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    throw new Error(`Clear request failed with status ${response.status}`);
  }

  return response.json();
}

export async function fetchMcpTools(backendUrl) {
  const response = await fetch(`${backendUrl}/mcp/tools`);

  if (!response.ok) {
    throw new Error(`MCP tools request failed with status ${response.status}`);
  }

  return response.json();
}

export async function fetchSkills(backendUrl) {
  const response = await fetch(`${backendUrl}/skills`);

  if (!response.ok) {
    throw new Error(`Skills request failed with status ${response.status}`);
  }

  return response.json();
}
