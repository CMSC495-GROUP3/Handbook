/**
 * Frontend configuration.
 *
 * APP_NAME is the product-name source of truth for the client. To rebrand,
 * change it here, in sourcebook/rag/config.py on the Python side, and in
 * the <title> tag in index.html.
 */
export const APP_NAME = 'Sourcebook'

/** Heading on the empty chat state, before the first question. */
export const APP_HEADLINE = 'What does the policy say?'

/** Line under the heading on the empty chat state. */
export const APP_TAGLINE =
  'Ask about company policy and get an answer with its source. If nothing matches, it says so instead of guessing.'

/** localStorage key holding the JWT. */
export const TOKEN_KEY = 'sourcebook_token'

/**
 * The `cred` claim of a session opened with the Human Resources password.
 * Mirrors HR_PASSWORD_HASH_VAR in sourcebook/api/routes/auth.py; change both
 * together.
 */
export const HR_CRED = 'HR_PASSWORD_HASH'

/**
 * Who a refused or unhelpful answer is handed to. Mirrors ESCALATION_CONTACT
 * in sourcebook/rag/config.py; change both together.
 */
export const ESCALATION_CONTACT = 'Human Resources'
