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

function makeClient(sessionToken = null) {
  return createClient(supabaseUrl, supabaseAnonKey, {
    global: {
      headers: sessionToken ? { 'x-cloudpos-session': sessionToken } : {},
    },
  });
}

// Export a live binding.  Recreating the client is necessary because the
// session token is sent as a request header used by the database RLS policy.
export let supabase = makeClient();

export function setCloudSession(sessionToken) {
  supabase = makeClient(sessionToken);
}

export function clearCloudSession() {
  supabase = makeClient();
}
