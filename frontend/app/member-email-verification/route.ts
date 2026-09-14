// Replace with authenticated team email verification service when available.
// Never issue a pretend code or mark an unverified address as verified.
export async function POST() {
  return Response.json({ error: "이메일 인증 서비스 연결 전이에요. 아직 인증 코드를 발송할 수 없으며 기존 이메일은 유지돼요." }, { status: 503, headers: { "Cache-Control": "no-store" } });
}
