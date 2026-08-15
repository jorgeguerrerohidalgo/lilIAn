let raw = "";
process.stdin.on("data", (chunk) => (raw += chunk));
process.stdin.on("end", () => {
  let input;
  try {
    input = JSON.parse(raw);
  } catch {
    process.exit(0);
  }

  const path = input?.tool_input?.file_path ?? "";
  const name = path.split("/").pop() ?? "";

  // .env.example y .env.production.example son plantillas sin secretos.
  const isEnvFile = /^\.env($|\.)/.test(name) && !name.endsWith(".example");

  if (isEnvFile) {
    console.error(
      `[Hook] BLOQUEADO: ${name} contiene secretos reales (JWT_SECRET, DATABASE_URL).\n` +
        `[Hook] Edítalo tú mismo, o usa 'vercel env' / 'railway variables' para los entornos desplegados.`,
    );
    process.exit(2);
  }

  process.exit(0);
});
