import Link from "next/link";

export default function AdminHomePage() {
  return (
    <main className="flex flex-1 items-center justify-center px-6 text-center">
      <div>
        <h1 className="text-xl font-semibold">Admin</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          <Link href="/admin/users" className="underline">
            User management
          </Link>{" "}
          is live (Sprint 1). The ECAEP editorial workspace lands in Sprint 3.
        </p>
      </div>
    </main>
  );
}
