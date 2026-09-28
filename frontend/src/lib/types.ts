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

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type Grade = "G10" | "G11" | "G12";
export type StudentType = "academy" | "external";
export type SubscriptionStatus = "active" | "pending" | "expired" | "suspended";

export interface StudentRow {
  id: number;
  full_name: string;
  student_code: string | null;
  email: string | null;
  grade_level: Grade | null;
  student_type: StudentType;
  effective_subscription: SubscriptionStatus;
  guardian_phone: string;
  is_active: boolean;
  last_login_at: string | null;
  groups_count: number;
  courses_count: number;
  total_points: number;
}

export interface StudentGroupSummary {
  id: number;
  name: string;
}

export interface StudentEnrollment {
  course_id: number;
  course_title: string;
  expires_at: string | null;
  source: "direct" | "group";
}

export interface StudentDetail extends StudentRow {
  admin_notes: string;
  subscription_status: SubscriptionStatus;
  subscription_expires_at: string | null;
  created_at: string;
  groups: StudentGroupSummary[];
  enrollments: StudentEnrollment[];
}

export interface StudentCreateInput {
  student_code: string;
  full_name: string;
  email?: string | null;
  guardian_phone?: string;
  grade_level?: Grade | null;
  student_type?: StudentType;
  subscription_status?: SubscriptionStatus;
  subscription_expires_at?: string | null;
  admin_notes?: string;
  password?: string | null;
  course_ids?: number[];
  group_ids?: number[];
}

export type StudentUpdateInput = Partial<Omit<StudentCreateInput, "password" | "course_ids" | "group_ids">> & {
  is_active?: boolean;
};

export interface StudentCreateResponse {
  student: StudentDetail;
  generated_password: string | null;
}

export type StudentBulkActionType = "activate" | "deactivate" | "add_to_group" | "remove_from_group" | "enroll" | "unenroll" | "delete";

export interface StudentBulkActionInput {
  student_ids: number[];
  action: StudentBulkActionType;
  group_id?: number | null;
  course_id?: number | null;
  expires_at?: string | null;
}

export interface DeletePreview {
  enrollments: number;
  groups: number;
  attempts: number;
  attendance: number;
  points: number;
  progress: number;
}

export interface ImportRowResult {
  row_no: number;
  data: Record<string, string | null>;
  errors: string[];
  warnings: string[];
}

export interface ImportPreview {
  rows: ImportRowResult[];
  valid_count: number;
  error_count: number;
}

export interface ImportCommitResult {
  created: { row_no: number; id: number; student_code: string; full_name: string; generated_password: string | null }[];
  failed: { row_no: number; errors: string[] }[];
}

export interface AdminGroupCourse {
  id: number;
  title: string;
  expires_at: string | null;
}

export interface AdminGroup {
  id: number;
  name: string;
  description: string;
  members_count: number;
  courses: AdminGroupCourse[];
}

export interface AdminCourse {
  id: number;
  title: string;
  subject: string;
  level: string;
  accent: string;
  is_published: boolean;
  lesson_count: number;
  student_count: number;
}
