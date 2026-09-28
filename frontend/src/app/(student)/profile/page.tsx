"use client";

import Link from "next/link";
import { IdCard, KeyRound, Mail, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/hooks/use-auth";

// Full profile editing (guardian phone, notification prefs, etc.) ships in a later phase. For now
// this is the entry point for the optional, self-service "change password" flow.
export default function ProfilePage() {
  const { data: me, isLoading } = useMe();

  return (
    <div>
      <h1 className="text-h1">الملف الشخصي</h1>

      {isLoading ? (
        <Skeleton className="mt-6 h-32 w-full max-w-md" />
      ) : me ? (
        <div className="mt-6 flex max-w-md flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserRound size={18} /> {me.full_name}
              </CardTitle>
              <CardDescription>{me.grade_level ? `${me.grade_level} · ` : ""}{me.student_type === "external" ? "طالب خارجي" : "طالب الأكاديمية"}</CardDescription>
            </CardHeader>
            <div className="flex flex-col gap-2 text-body-sm text-text-muted">
              {me.student_code ? (
                <span className="flex items-center gap-2 ltr">
                  <IdCard size={15} /> {me.student_code}
                </span>
              ) : null}
              {me.email ? (
                <span className="flex items-center gap-2 ltr">
                  <Mail size={15} /> {me.email}
                </span>
              ) : null}
            </div>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <KeyRound size={18} /> الأمان
              </CardTitle>
              <CardDescription>غيّر كلمة مرورك في أي وقت تحب.</CardDescription>
            </CardHeader>
            <Button asChild variant="secondary">
              <Link href="/change-password">تغيير كلمة المرور</Link>
            </Button>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
