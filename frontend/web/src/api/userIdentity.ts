const configuredUserId =
  import.meta.env
    .VITE_DEMO_USER_ID
    ?.trim();


export const CURRENT_USER_ID =
  configuredUserId
  || "user-001";


export function getIdentityHeaders():
  Record<string, string> {
  return {
    "X-User-ID":
      CURRENT_USER_ID,
  };
}