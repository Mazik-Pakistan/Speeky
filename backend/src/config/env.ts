import "dotenv/config";

function required(key: string): string {
  const value = process.env[key];
  if (!value) throw new Error(`Missing required env var: ${key}`);

  return value;
}

export const env = {
  PORT: Number(process.env.PORT ?? 8000),
  SUPABASE_URL: required("SUPABASE_URL"),
  SUPABASE_SECRET_KEY: required("SUPABASE_SECRET_KEY"),
  CLIENT_ORIGINS: (process.env.CLIENT_ORIGINS ?? "http://localhost:3000")
    .split(",")
    .map((o) => o.trim())
    .filter(Boolean),
};
