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

export type CourseAccent = "blue" | "navy" | "sky" | "teal" | "gold" | "violet" | "rose";
export type MaterialType = "pdf" | "link" | "file";

export interface CourseIn {
  title: string;
  subtitle?: string;
  description?: string;
  subject?: string;
  level?: string;
  accent?: CourseAccent;
  cover_file_id?: string | null;
  is_published?: boolean;
}

export type CoursePatch = Partial<CourseIn>;

export interface AdminMaterial {
  id: number;
  title: string;
  material_type: MaterialType;
  url: string | null;
  file_id: string | null;
  is_downloadable: boolean;
  position: number;
}

export interface AdminLesson {
  id: number;
  title: string;
  description: string;
  duration_minutes: number;
  recording_url: string | null;
  position: number;
  is_preview: boolean;
  materials: AdminMaterial[];
}

export interface AdminSection {
  id: number;
  title: string;
  position: number;
  lessons: AdminLesson[];
}

export interface AdminCourseDetail {
  id: number;
  title: string;
  subtitle: string;
  description: string;
  subject: string;
  level: string;
  accent: string;
  cover_file_id: string | null;
  cover_url: string | null;
  is_published: boolean;
  student_count: number;
  lesson_count: number;
  sections: AdminSection[];
}

export interface CourseDeletePreview {
  sections: number;
  lessons: number;
  materials: number;
  enrollments: number;
  exams: number;
  live_sessions: number;
  students_with_progress: number;
}

export interface CourseStudentRow {
  student_id: number;
  full_name: string;
  student_code: string | null;
  source: "direct" | "group";
  source_label: string;
  progress: number;
}

export interface FileOut {
  id: string;
  purpose: string;
  content_type: string;
  size_bytes: number;
  original_name: string;
}

// ------------------------------------------------------------------------------- student ----

export interface CourseCard {
  id: number;
  title: string;
  subtitle: string;
  subject: string;
  level: string;
  accent: string;
  cover_url: string | null;
  progress: number;
  lesson_count: number;
  completed_count: number;
}

export interface StudentLessonSummary {
  id: number;
  title: string;
  duration_minutes: number;
  completed: boolean;
  is_preview: boolean;
  has_recording: boolean;
  materials_count: number;
}

export interface StudentSection {
  id: number;
  title: string;
  lessons: StudentLessonSummary[];
}

export interface CourseDetail {
  course: CourseCard;
  sections: StudentSection[];
}

export interface RecordedLessonRow {
  id: number;
  title: string;
  duration_minutes: number;
  completed: boolean;
}

export interface RecordedLessonsGroup {
  course_id: number;
  course_title: string;
  lessons: RecordedLessonRow[];
}

export interface StudentMaterial {
  id: number;
  title: string;
  material_type: MaterialType;
  url: string | null;
  is_downloadable: boolean;
}

export interface Recording {
  url: string;
  embed_url: string | null;
  kind: "youtube" | "drive" | "zoom" | "other";
}

export interface LessonDetail {
  id: number;
  title: string;
  description: string;
  course_id: number;
  course_title: string;
  recording: Recording | null;
  materials: StudentMaterial[];
  prev_id: number | null;
  next_id: number | null;
  completed: boolean;
}

// ------------------------------------------------------------------------ live sessions ----

export type AttendanceStatus = "present" | "late" | "absent" | "excused" | "unmarked";
export type LiveSessionStatusFilter = "upcoming" | "live" | "ended";

export interface LiveSessionIn {
  title: string;
  description?: string;
  course_id: number;
  group_id?: number | null;
  provider?: string;
  join_url: string;
  starts_at: string;
  ends_at: string;
  recording_url?: string | null;
  is_active?: boolean;
}

export type LiveSessionPatch = Partial<LiveSessionIn>;

export interface AttendanceSummary {
  present: number;
  late: number;
  absent: number;
  excused: number;
  unmarked: number;
}

export interface AdminLiveSession {
  id: number;
  title: string;
  description: string;
  course_id: number;
  course_title: string;
  group_id: number | null;
  group_name: string | null;
  provider: string;
  join_url: string;
  starts_at: string;
  ends_at: string;
  recording_url: string | null;
  is_active: boolean;
  attendance_finalized_at: string | null;
  audience_count: number;
  attendance: AttendanceSummary;
}

export interface AttendanceRow {
  student_id: number;
  full_name: string;
  student_code: string | null;
  grade_level: string | null;
  status: AttendanceStatus;
  source: string | null;
  joined_at: string | null;
  note: string;
}

export interface AttendanceSheet {
  session: AdminLiveSession;
  counts: AttendanceSummary;
  students: AttendanceRow[];
}

export interface MyAttendance {
  status: AttendanceStatus;
  joined_at: string | null;
}

export interface LiveSessionCard {
  id: number;
  title: string;
  course_id: number;
  course_title: string;
  provider: string;
  starts_at: string;
  ends_at: string;
  recording_url: string | null;
  can_join: boolean;
  join_opens_at: string;
  my_attendance: MyAttendance;
}

export interface JoinResponse {
  join_url: string;
  attendance_status: "present" | "late" | "absent" | "excused";
}

// -------------------------------------------------------------------------------------- exams ----

export type ExamMode = "full" | "answer_sheet";
export type QuestionType = "image_mcq" | "text_mcq" | "bubble";
export type Difficulty = "easy" | "medium" | "hard";
export type ChoiceLabel = "A" | "B" | "C" | "D";
export type ExamState = "draft" | "upcoming" | "available" | "ended";

export interface ExamIn {
  title: string;
  description?: string;
  course_id: number;
  group_id?: number | null;
  exam_mode?: ExamMode;
  duration_minutes?: number;
  passing_score?: number;
  max_attempts?: number;
  starts_at?: string | null;
  ends_at?: string | null;
}

export type ExamPatch = Partial<ExamIn>;

export interface AdminExamRow {
  id: number;
  title: string;
  course_title: string;
  group_name: string | null;
  exam_mode: ExamMode;
  state: ExamState;
  question_count: number;
  total_points: number;
  attempts_count: number;
  average_score: number | null;
  locked_count: number;
  starts_at: string | null;
  ends_at: string | null;
}

export interface ExamChoiceOut {
  id: number;
  label: ChoiceLabel;
  text: string;
  is_correct: boolean;
}

export interface ExamQuestionOut {
  id: number;
  question_type: QuestionType;
  position: number;
  prompt_text: string;
  image_url: string | null;
  topic: string;
  difficulty: Difficulty;
  points: number;
  passage_id: number | null;
  choices: ExamChoiceOut[];
}

export interface ExamPassageOut {
  id: number;
  title: string;
  body_text: string;
  image_url: string | null;
  position: number;
  question_ids: number[];
}

export interface PassageIn {
  title?: string;
  body_text?: string;
}

export type PassagePatch = PassageIn;

export interface AdminExamDetail {
  id: number;
  title: string;
  description: string;
  course_id: number;
  course_title: string;
  group_id: number | null;
  group_name: string | null;
  exam_mode: ExamMode;
  duration_minutes: number;
  passing_score: number;
  max_attempts: number;
  starts_at: string | null;
  ends_at: string | null;
  is_published: boolean;
  published_at: string | null;
  state: ExamState;
  has_attempts: boolean;
  question_count: number;
  total_points: number;
  questions: ExamQuestionOut[];
  passages: ExamPassageOut[];
}

export interface ExamDeletePreview {
  questions: number;
  attempts: number;
  answers: number;
  points_entries: number;
}

export interface ChoiceIn {
  label: ChoiceLabel;
  text: string;
}

export interface TextQuestionIn {
  question_type: "text_mcq";
  prompt_text: string;
  choices: ChoiceIn[];
  correct_label: ChoiceLabel;
  topic?: string;
  difficulty?: Difficulty;
  points?: number;
}

export interface QuestionPatch {
  prompt_text?: string;
  topic?: string;
  difficulty?: Difficulty;
  points?: number;
  choices?: ChoiceIn[];
  correct_label?: ChoiceLabel;
}

export interface AnswerKeyPreview {
  parsed: ChoiceLabel[];
  count: number;
  question_count: number;
  errors: string[];
}

export interface AnswerKeyApplyIn {
  answers: string;
  points_per_question?: number | null;
  publish?: boolean;
}

// ------------------------------------------------------------------------- student exam runner ----

export type AttemptStatus = "granted" | "in_progress" | "locked" | "submitted" | "expired" | "superseded";
export type StudentExamStatus = "upcoming" | "available" | "in_progress" | "submitted" | "expired" | "completed";
export type ViolationType = "page_hidden" | "window_blur" | "fullscreen_exit";

export interface LatestResult {
  percentage: number;
  score_points: number;
  total_points: number;
  submitted_at: string | null;
  passed: boolean;
}

export interface StudentExamCard {
  id: number;
  title: string;
  course_title: string;
  group_name: string | null;
  status: StudentExamStatus;
  duration: number;
  question_count: number;
  total_points: number;
  passing_score: number;
  max_attempts: number;
  attempts_used: number;
  best_score: number | null;
  latest: LatestResult | null;
  open_attempt_status: AttemptStatus | null;
  starts_at: string | null;
  ends_at: string | null;
}

export interface ExamPreStartOut extends StudentExamCard {
  exam_mode: ExamMode;
  description: string;
}

export interface AttemptChoiceOut {
  id: number;
  label: ChoiceLabel;
  text: string | null;
}

export interface AttemptQuestionOut {
  id: number;
  position: number;
  type: QuestionType;
  prompt_text: string | null;
  image_url: string | null;
  topic: string;
  difficulty: Difficulty;
  points: number;
  passage_id: number | null;
  choices: AttemptChoiceOut[];
}

export interface AttemptPassageOut {
  id: number;
  title: string;
  body_text: string;
  image_url: string | null;
  position: number;
}

export interface AttemptPayload {
  attempt_id: number;
  status: AttemptStatus;
  expires_at: string;
  server_now: string;
  violation_count: number;
  violation_limit: number;
  questions: AttemptQuestionOut[];
  passages: AttemptPassageOut[];
  saved_answers: Record<number, number | null>;
}

export interface AnswerIn {
  question_id: number;
  choice_id: number | null;
}

export interface AnswersUpsertOut {
  saved: boolean;
  server_now: string;
  expires_at: string;
}

export interface AttemptEventOut {
  violation_count: number;
  locked: boolean;
  message: string | null;
}

export interface ExamResult {
  attempt_id: number;
  exam_title: string;
  score_points: number;
  total_points: number;
  percentage: number;
  passed: boolean;
  submitted_at: string | null;
  points_awarded: number;
}
