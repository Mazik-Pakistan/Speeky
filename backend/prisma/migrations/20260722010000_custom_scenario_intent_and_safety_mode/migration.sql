-- AlterTable
ALTER TABLE "custom_scenarios" ADD COLUMN     "intent" TEXT NOT NULL DEFAULT '',
ADD COLUMN     "safetyMode" BOOLEAN NOT NULL DEFAULT false;
