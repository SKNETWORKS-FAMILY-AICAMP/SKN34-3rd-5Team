import RouteWriter from "@/components/route-writer";

export const metadata = { title: "나의 루트 만들기" };

export default async function NewRoutePage({
  searchParams,
}: {
  searchParams: Promise<{ edit?: string | string[]; copy?: string | string[]; stadium?: string | string[] }>;
}) {
  const query = await searchParams;
  return (
    <RouteWriter
      copyId={typeof query.copy === "string" ? query.copy : undefined}
      editId={typeof query.edit === "string" ? query.edit : undefined}
      initialStadium={typeof query.stadium === "string" ? query.stadium : undefined}
    />
  );
}
