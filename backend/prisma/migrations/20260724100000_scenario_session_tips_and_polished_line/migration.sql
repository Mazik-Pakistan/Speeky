-- AlterTable
ALTER TABLE "scenario_sessions" ADD COLUMN     "tips" TEXT[] DEFAULT ARRAY[]::TEXT[],
ADD COLUMN     "originalLine" TEXT,
ADD COLUMN     "polishedLine" TEXT;
