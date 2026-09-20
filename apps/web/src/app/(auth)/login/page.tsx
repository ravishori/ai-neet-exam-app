import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";

import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    <main className="flex flex-1 items-center justify-center px-6">
      <Suspense fallback={<Skeleton className="h-80 w-full max-w-sm rounded-xl" />}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
