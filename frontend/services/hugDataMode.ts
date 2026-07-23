/**
 * HUG 업무대장 조회 모드 결정 헬퍼.
 *
 * 백엔드는 운영 업무대장(LIVE)과 별도 업무대장(DEMO)을 어떤 경로에서도 합산하지 않으므로,
 * 목록·KPI 조회 시 한 모드를 골라야 한다. 화면은 LIVE를 우선 조회하고 결과가 비어 있으면
 * 다른 업무대장으로 한 번 폴백해, 어느 환경에서든 실제 존재하는 데이터를 보여준다.
 */

export type HugDataMode = "LIVE" | "DEMO";

/** fetcher(mode)를 LIVE→DEMO 순으로 시도해 처음으로 비어 있지 않은 응답을 반환한다. */
export async function withModeFallback<T>(
  fetcher: (mode: HugDataMode) => Promise<T>,
  isEmpty: (data: T) => boolean,
): Promise<{ data: T; mode: HugDataMode }> {
  const live = await fetcher("LIVE");
  if (!isEmpty(live)) return { data: live, mode: "LIVE" };
  try {
    const demo = await fetcher("DEMO");
    if (!isEmpty(demo)) return { data: demo, mode: "DEMO" };
  } catch {
    /* DEMO 조회 실패 시 LIVE 빈 응답 유지 */
  }
  return { data: live, mode: "LIVE" };
}
