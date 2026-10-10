// What the app may show when something goes wrong. Only messages written for people reach the
// screen: the app's own (ShownError) and the server's (ApiError, which extends it). Anything else
// (a library's message, a status code, a stack trace) shows a plain fallback instead.

/** An error whose message is written for the person using the app. */
export class ShownError extends Error {}

export function errorText(e: unknown, fallback = 'Something went wrong. Try again.'): string {
  return e instanceof ShownError && e.message ? e.message : fallback
}
