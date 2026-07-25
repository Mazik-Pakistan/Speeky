-- AlterTable
ALTER TABLE "users" ADD COLUMN     "lifetimePracticeSeconds" DOUBLE PRECISION NOT NULL DEFAULT 0,
ADD COLUMN     "unlockedMilestoneHours" INTEGER[] DEFAULT ARRAY[]::INTEGER[];

-- CreateTable
CREATE TABLE "vocabulary_word_progress" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "word" TEXT NOT NULL,
    "useCount" INTEGER NOT NULL DEFAULT 0,
    "status" TEXT NOT NULL DEFAULT 'learning',
    "needsReview" BOOLEAN NOT NULL DEFAULT false,
    "lastUsedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "vocabulary_word_progress_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "vocabulary_word_progress_userId_status_idx" ON "vocabulary_word_progress"("userId", "status");

-- CreateIndex
CREATE UNIQUE INDEX "vocabulary_word_progress_userId_word_key" ON "vocabulary_word_progress"("userId", "word");

-- AddForeignKey
ALTER TABLE "vocabulary_word_progress" ADD CONSTRAINT "vocabulary_word_progress_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
