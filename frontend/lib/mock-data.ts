import {
  MessagesSquare,
  Briefcase,
  Mic2,
  Building2,
  Gauge,
  Route,
  TrendingUp,
  Flame,
  Sparkles,
  Timer,
} from "lucide-react";
import type {
  NavLink,
  FeatureItem,
  ComparisonPoint,
  StepItem,
  StatCard,
  Testimonial,
  FaqItem,
  TrustIndicator,
} from "./types";

export const NAV_LINKS: NavLink[] = [
  { label: "Features", href: "#features" },
  { label: "Why Speeky", href: "#why-speeky" },
  { label: "Testimonials", href: "#testimonials" },
  { label: "FAQ", href: "#faq" },
];

export const TRUST_INDICATORS: TrustIndicator[] = [
  { id: "learners", label: "Built for job seekers & professionals" },
  { id: "sessions", label: "Practice sessions available 24/7" },
  { id: "privacy", label: "Judgment-free, private practice" },
];

export const CORE_FEATURES: FeatureItem[] = [
  {
    id: "conversation-practice",
    icon: MessagesSquare,
    title: "AI Conversation Practice",
    description:
      "Speak with an AI partner over voice or text on real-life topics, anytime you want to practice.",
  },
  {
    id: "interview-coach",
    icon: Briefcase,
    title: "Interview Coach",
    description:
      "Run mock interviews across HR, technical, and visa formats with realistic follow-up questions.",
  },
  {
    id: "pronunciation-analysis",
    icon: Mic2,
    title: "Pronunciation Analysis",
    description:
      "Get word-level feedback on pronunciation instead of a single, vague overall score.",
  },
  {
    id: "workplace-communication",
    icon: Building2,
    title: "Workplace Communication",
    description:
      "Practice emails, meetings, and client conversations framed around workplace tone and clarity.",
  },
  {
    id: "confidence-score",
    icon: Gauge,
    title: "Confidence Score",
    description:
      "One top-line score that tracks confidence, fluency, vocabulary, and pronunciation together.",
  },
  {
    id: "learning-path",
    icon: Route,
    title: "Personalized Learning Path",
    description:
      "A starting level and practice plan built from your goals and your initial assessment.",
  },
];

export const COMPARISON_POINTS: ComparisonPoint[] = [
  {
    id: "focus",
    traditional: "Focuses on grammar rules and vocabulary lists",
    speeky: "Focuses on real conversations and speaking confidence",
  },
  {
    id: "format",
    traditional: "Static lessons and quizzes",
    speeky: "Live AI conversations that respond and adapt",
  },
  {
    id: "outcome",
    traditional: "Measures correctness",
    speeky: "Measures confidence, fluency, and clarity",
  },
  {
    id: "context",
    traditional: "Generic textbook scenarios",
    speeky: "Interviews, meetings, and workplace situations",
  },
];

export const HOW_IT_WORKS: StepItem[] = [
  {
    id: "sign-up",
    index: 1,
    title: "Sign Up",
    description: "Create an account and tell Speeky what you're working toward.",
  },
  {
    id: "assessment",
    index: 2,
    title: "Complete Assessment",
    description: "A short, AI-led speaking assessment sets your starting point.",
  },
  {
    id: "practice",
    index: 3,
    title: "Practice with AI",
    description: "Have real conversations, mock interviews, and workplace scenarios.",
  },
  {
    id: "track",
    index: 4,
    title: "Track Progress",
    description: "Watch your confidence, fluency, and vocabulary scores grow.",
  },
  {
    id: "confidence",
    index: 5,
    title: "Build Confidence",
    description: "Walk into interviews, meetings, and conversations ready.",
  },
];

export const PROGRESS_STATS: StatCard[] = [
  {
    id: "confidence-score",
    icon: Gauge,
    label: "Confidence Score",
    value: "82",
    delta: "+6 this month",
    trend: "up",
  },
  {
    id: "speaking-progress",
    icon: TrendingUp,
    label: "Speaking Progress",
    value: "68%",
    delta: "+12% this month",
    trend: "up",
  },
  {
    id: "weekly-improvement",
    icon: Sparkles,
    label: "Weekly Improvement",
    value: "+9%",
    delta: "vs. last week",
    trend: "up",
  },
  {
    id: "streak",
    icon: Flame,
    label: "Streak",
    value: "14 days",
    delta: "Personal best",
    trend: "neutral",
  },
  {
    id: "ai-feedback",
    icon: Timer,
    label: "AI Feedback",
    value: "3 new notes",
    delta: "From last session",
    trend: "neutral",
  },
];

export const TESTIMONIALS: Testimonial[] = [
  {
    id: "amara",
    name: "Amara K.",
    role: "MBA Candidate",
    quote:
      "I used Speeky to prepare for admission interviews. Practicing out loud with the AI made the real interview feel familiar instead of terrifying.",
    initials: "AK",
  },
  {
    id: "daniyal",
    name: "Daniyal R.",
    role: "Software Engineer",
    quote:
      "The interview coach asked follow-up questions I didn't expect, which is exactly what happened in my real technical interview a week later.",
    initials: "DR",
  },
  {
    id: "sara",
    name: "Sara M.",
    role: "Marketing Associate",
    quote:
      "My meetings used to stress me out. A few weeks of workplace scenario practice and I speak up first instead of last.",
    initials: "SM",
  },
  {
    id: "hamza",
    name: "Hamza T.",
    role: "Recent Graduate",
    quote:
      "I liked that it never felt like a grammar app. It felt like practicing with someone who was actually listening.",
    initials: "HT",
  },
];

export const FAQ_ITEMS: FaqItem[] = [
  {
    id: "what-is-speeky",
    question: "Is Speeky a language-learning app?",
    answer:
      "No. Speeky is an AI communication coach. It's built for people who already know English but want to speak with more confidence in interviews, meetings, and everyday conversations — not for grammar lessons.",
  },
  {
    id: "how-it-works",
    question: "How does the AI conversation practice work?",
    answer:
      "You speak or type with the AI on real-life topics, interview scenarios, or workplace situations. The AI responds naturally, keeps the conversation going, and gives you feedback afterward.",
  },
  {
    id: "assessment",
    question: "What happens during the initial assessment?",
    answer:
      "A short, five-minute AI-led conversation evaluates your fluency, pronunciation, confidence, and vocabulary, then sets your starting point and personalized learning path.",
  },
  {
    id: "who-is-it-for",
    question: "Who is Speeky built for?",
    answer:
      "University students, fresh graduates, job seekers, and working professionals who want to communicate more confidently in English, especially in interviews and at work.",
  },
  {
    id: "device",
    question: "Do I need any special equipment?",
    answer:
      "No. A device with a microphone is enough to practice with voice, and text mode is always available as an alternative.",
  },
];
