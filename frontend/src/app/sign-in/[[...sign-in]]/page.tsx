import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center mb-8">
        <SignIn afterSignInUrl="/dashboard" />
      </div>
    </div>
  );
}
