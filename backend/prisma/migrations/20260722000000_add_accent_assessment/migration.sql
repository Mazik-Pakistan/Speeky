-- CreateTable
CREATE TABLE "accent_assessments" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "monthIndex" INTEGER NOT NULL,
    "pronunciationScore" DOUBLE PRECISION NOT NULL,
    "wordStressScore" DOUBLE PRECISION NOT NULL,
    "intonationScore" DOUBLE PRECISION NOT NULL,
    "clarityScore" DOUBLE PRECISION NOT NULL,
    "completedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "accent_assessments_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "accent_assessments_userId_monthIndex_idx" ON "accent_assessments"("userId", "monthIndex");

-- AddForeignKey
ALTER TABLE "accent_assessments" ADD CONSTRAINT "accent_assessments_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
