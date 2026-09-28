export type Role = "admin" | "student";

export interface Me {
  id: number;
  role: Role;
  full_name: string;
  student_code: string | null;
  email: string | null;
  grade_level: "G10" | "G11" | "G12" | null;
  student_type: "academy" | "external" | null;
  must_change_password: boolean;
}

export interface LoginResponse {
  user: Me;
  must_change_password: boolean;
}

export interface Branding {
  display_name: string;
  logo_url: string | null;
  primary_color: string;
  accent_color: string;
  whatsapp_url: string;
}
