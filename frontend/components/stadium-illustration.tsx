export function StadiumIllustration({ dome }: { dome: boolean }) {
  return <svg viewBox="0 0 360 190" className="info-stadium-illustration" aria-hidden="true">
    <circle cx="283" cy="44" r="24" fill="currentColor" opacity=".1" />
    <path d="M35 157H327" stroke="currentColor" opacity=".13" strokeWidth="2" />
    <path d="M48 88V143M310 88V143" stroke="currentColor" opacity=".4" strokeWidth="4" />
    <rect x="32" y="76" width="33" height="13" rx="3" fill="currentColor" opacity=".4" /><rect x="294" y="76" width="33" height="13" rx="3" fill="currentColor" opacity=".4" />
    {dome ? <path d="M70 116C70 22 290 22 290 116" fill="currentColor" opacity=".16" stroke="currentColor" strokeWidth="3" /> : <path d="M74 98Q180 21 286 98L270 131H91Z" fill="currentColor" opacity=".18" />}
    <ellipse cx="180" cy="120" rx="113" ry="37" fill="white" />
    <ellipse cx="180" cy="118" rx="101" ry="30" fill="currentColor" opacity=".2" />
    <ellipse cx="180" cy="121" rx="76" ry="22" fill="#83bca9" opacity=".65" />
    <path d="M180 139L148 120L180 100L212 120Z" fill="#e5ccb2" stroke="white" strokeWidth="2" /><path d="M180 136L159 122L180 108L201 122Z" fill="#8eba9b" />
    <path d="M67 121V139C67 187 293 187 293 139V121C293 169 67 169 67 121Z" fill="currentColor" opacity=".23" />
    <path d="M67 133C84 175 282 175 293 133" stroke="currentColor" fill="none" opacity=".3" />
    <path d="M101 148V160M128 155V167M156 158V170M185 159V171M214 157V169M243 152V165M271 143V156" stroke="white" opacity=".65" strokeWidth="3" />
    <path d="M180 63V35L199 42L180 49" stroke="currentColor" fill="currentColor" strokeWidth="2" opacity=".6" />
  </svg>;
}
