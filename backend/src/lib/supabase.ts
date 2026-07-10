import { createClient } from "@supabase/supabase-js";
import { env } from "../config/env";
export default createClient(env.SUPABASE_URL, env.SUPABASE_SECRET_KEY);
