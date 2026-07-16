/**
 * 화면 단위 상태 9종(Frontend_UIUX_명세서 9장). 화면마다 이 중 해당하는 상태만 구현한다.
 */
export const UIState = {
  LOADING: "loading",
  SUCCESS: "success",
  PARTIAL: "partial",
  ERROR: "error",
  EMPTY: "empty",
  UNAUTHORIZED: "unauthorized",
  NOT_FOUND: "not_found",
  TIMEOUT: "timeout",
  MOCK: "mock",
} as const;
export type UIState = (typeof UIState)[keyof typeof UIState];
