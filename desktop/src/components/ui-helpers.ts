export type Variant = "primary" | "secondary" | "ghost" | "soft" | "danger" | "danger-soft";
export type Size = "sm" | "md" | "lg";

export function buttonClass(variant: Variant = "secondary", size: Size = "md", extra = ""): string {
  return ["btn", `btn--${variant}`, size !== "md" ? `btn--${size}` : "", extra].filter(Boolean).join(" ");
}

const AVATAR_TONES = ["olive", "sand", "blue", "rose", "violet", "slate"];

export function avatarTone(name: string): string {
  let hash = 0;
  for (let index = 0; index < name.length; index += 1) {
    hash = (hash * 31 + name.charCodeAt(index)) % 997;
  }
  return AVATAR_TONES[hash % AVATAR_TONES.length];
}
