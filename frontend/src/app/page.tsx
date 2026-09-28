import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";

// Simple branded entry page that leads to login (spec §13: the marketing landing page itself is
// out of scope for now — this is just the "leads to login" placeholder it asks for).
export default function Home() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-8 bg-bg px-4 text-center">
      <Brand />
      <div className="flex flex-col items-center gap-2">
        <h1 className="text-display">Talent Academy</h1>
        <p className="max-w-md text-body-lg text-text-muted">منصة الأكاديمية لطلاب الدبلومة الأمريكية — EST · SAT · ACT</p>
      </div>
      <Button asChild size="lg">
        <Link href="/login">
          دخول المنصة <ArrowLeft size={18} className="rtl-flip" />
        </Link>
      </Button>
    </main>
  );
}
