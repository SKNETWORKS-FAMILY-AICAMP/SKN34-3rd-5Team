import Image from "next/image";

const logoCodes = new Set(["LG", "HH", "SK", "SS", "NC", "KT", "LT", "HT", "OB", "WO"]);

export function TeamLogo({ code, name, className }: { code: string; name: string; className: string }) {
  const teamCode = code.toUpperCase();
  const hasLogo = logoCodes.has(teamCode);

  return (
    <span className={className} aria-hidden="true" style={hasLogo ? { background: "transparent", borderColor: "transparent" } : undefined}>
      {hasLogo ? (
        <Image
          src={`/images/teams/${teamCode.toLowerCase()}.svg`}
          alt=""
          width={96}
          height={96}
          style={{ display: "block", width: "100%", height: "100%", objectFit: "contain" }}
        />
      ) : name.slice(0, 2)}
    </span>
  );
}
