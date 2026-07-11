import Image from "next/image";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <Image src="/images/logo.png" alt="lilIAn Logo" width={80} height={80} />
          </div>
          <h1 className="text-3xl font-bold text-primary-700">lilIAn</h1>
          <p className="text-gray-600 mt-2">Plataforma legaltech chilena</p>
        </div>
        {children}
      </div>
    </div>
  );
}
