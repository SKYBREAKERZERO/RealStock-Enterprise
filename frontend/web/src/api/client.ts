const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL
  ?? ""
)
  .trim()
  .replace(
    /\/+$/,
    "",
  );


const DEMO_USER_ID = (
  import.meta.env.VITE_DEMO_USER_ID
  ?? ""
)
  .trim();


export function apiUrl(
  path: string,
): string {
  /*
   * Preserve absolute URLs.
   *
   * This allows callers to explicitly
   * provide an external URL when needed.
   */
  if (
    /^https?:\/\//i.test(
      path,
    )
  ) {
    return path;
  }

  /*
   * API paths inside RealStock should
   * normally begin with "/".
   *
   * Normalising here prevents callers
   * from having to care whether they
   * passed:
   *
   *   api/v1/watchlist
   *
   * or:
   *
   *   /api/v1/watchlist
   */
  const normalizedPath =
    path.startsWith("/")
      ? path
      : `/${path}`;

  /*
   * When VITE_API_BASE_URL is empty:
   *
   *   /api/v1/watchlist
   *
   * This supports the Docker/nginx
   * same-origin reverse proxy.
   *
   * LocalStack example:
   *
   *   VITE_API_BASE_URL=
   *     http://127.0.0.1:18000
   *
   * becomes:
   *
   *   http://127.0.0.1:18000
   *   /api/v1/watchlist
   *
   * Production example:
   *
   *   VITE_API_BASE_URL=
   *     https://api.realstock.com
   */
  return (
    `${API_BASE_URL}`
    + normalizedPath
  );
}


export class ApiError
  extends Error {
  readonly status: number;

  readonly payload:
    unknown;


  constructor(
    message: string,
    status: number,
    payload: unknown,
  ) {
    super(
      message,
    );

    this.name =
      "ApiError";

    this.status =
      status;

    this.payload =
      payload;
  }
}


type ApiMethod =
  | "GET"
  | "POST"
  | "PUT"
  | "PATCH"
  | "DELETE";


interface ApiRequestOptions {
  method?: ApiMethod;

  signal?: AbortSignal;

  headers?: HeadersInit;

  body?: unknown;
}


async function parseResponse(
  response: Response,
): Promise<unknown> {
  if (
    response.status
    === 204
  ) {
    return null;
  }

  const text =
    await response.text();

  if (!text) {
    return null;
  }

  const contentType =
    response.headers.get(
      "content-type",
    );

  if (
    contentType
      ?.toLowerCase()
      .includes(
        "application/json",
      )
  ) {
    try {
      return JSON.parse(
        text,
      ) as unknown;

    } catch {
      return text;
    }
  }

  return text;
}


function getErrorMessage(
  payload: unknown,
  status: number,
): string {
  if (
    typeof payload
      === "object"
    &&
    payload !== null
    &&
    "detail" in payload
  ) {
    const detail =
      (
        payload as {
          detail?: unknown;
        }
      ).detail;

    if (
      typeof detail
        === "string"
      &&
      detail.trim()
    ) {
      return detail;
    }
  }

  if (
    typeof payload
      === "string"
    &&
    payload.trim()
  ) {
    return payload;
  }

  return (
    `API request failed `
    + `with status ${status}`
  );
}


export async function apiRequest<T>(
  path: string,
  options:
    ApiRequestOptions = {},
): Promise<T> {
  const headers =
    new Headers(
      options.headers,
    );

  if (
    !headers.has(
      "Accept",
    )
  ) {
    headers.set(
      "Accept",
      "application/json",
    );
  }

  /*
   * Local/demo identity.
   *
   * The backend currently uses X-User-ID
   * as the development/demo identity
   * boundary for user-scoped resources
   * such as Watchlist and News.
   *
   * Do not hard-code user-001 here.
   * The identity is supplied through:
   *
   *   VITE_DEMO_USER_ID
   *
   * A future Cognito/OIDC integration can
   * replace this mechanism centrally.
   *
   * Explicit caller headers always win.
   */
  if (
    DEMO_USER_ID
    &&
    !headers.has(
      "X-User-ID",
    )
  ) {
    headers.set(
      "X-User-ID",
      DEMO_USER_ID,
    );
  }

  let body:
    BodyInit
    | undefined;

  if (
    options.body
    !== undefined
  ) {
    if (
      !headers.has(
        "Content-Type",
      )
    ) {
      headers.set(
        "Content-Type",
        "application/json",
      );
    }

    body =
      JSON.stringify(
        options.body,
      );
  }

  const response =
    await fetch(
      apiUrl(
        path,
      ),
      {
        method:
          options.method
          ?? "GET",

        headers,

        body,

        signal:
          options.signal,
      },
    );

  const payload =
    await parseResponse(
      response,
    );

  if (!response.ok) {
    throw new ApiError(
      getErrorMessage(
        payload,
        response.status,
      ),
      response.status,
      payload,
    );
  }

  return payload as T;
}


export function apiGet<T>(
  path: string,
  signal?: AbortSignal,
  headers?: HeadersInit,
): Promise<T> {
  return apiRequest<T>(
    path,
    {
      method:
        "GET",

      signal,

      headers,
    },
  );
}


export function apiPost<
  TResponse,
  TBody = unknown,
>(
  path: string,
  body: TBody,
  signal?: AbortSignal,
  headers?: HeadersInit,
): Promise<TResponse> {
  return apiRequest<TResponse>(
    path,
    {
      method:
        "POST",

      body,

      signal,

      headers,
    },
  );
}


export async function apiDelete(
  path: string,
  signal?: AbortSignal,
  headers?: HeadersInit,
): Promise<void> {
  await apiRequest<null>(
    path,
    {
      method:
        "DELETE",

      signal,

      headers,
    },
  );
}