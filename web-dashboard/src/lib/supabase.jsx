import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Supabase credentials not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in .env');
}

try {
  new URL(supabaseUrl);
} catch {
  throw new Error(`Invalid Supabase URL: ${supabaseUrl}. Must be a valid URL.`);
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
