export type CommunityPostNumber = string;

/** Formats fixtures only. Real six-digit numbers are issued once by the backend. */
export function formatCommunityPostNumber(sequence: string): CommunityPostNumber {
  if (!/^[1-9]\d{0,5}$/.test(sequence)) throw new Error("Expected a sequence between 1 and 999999");
  return sequence.padStart(6, "0");
}
