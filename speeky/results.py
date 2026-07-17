"""
Baseline Assessment Results Summary View implementation (BAS-US-01).

This module provides the results summary screen that displays assessment outcomes
in an encouraging, positive manner framing scores as starting points rather than grades.
"""

import logging
from typing import Dict, Optional
from datetime import datetime

try:
    from .storage import InMemoryStorage, LearningLevel, BaselineAssessment
    from .confidence import ConfidenceScoreEngine
except ImportError:
    from storage import InMemoryStorage, LearningLevel, BaselineAssessment
    from confidence import ConfidenceScoreEngine

logger = logging.getLogger(__name__)


class ResultsSummaryView:
    """
    Baseline Assessment Results Summary View.
    
    Displays clear, encouraging summary of initial assessment results
    immediately after completion.
    """
    
    def __init__(self, storage: InMemoryStorage, confidence_engine: ConfidenceScoreEngine):
        """
        Initialize results summary view.
        
        Args:
            storage: In-memory storage
            confidence_engine: Confidence score engine
        """
        self.storage = storage
        self.confidence_engine = confidence_engine
        
        logger.info("Results Summary View initialized")
    
    def generate_assessment_summary(self, assessment_id: str) -> Dict:
        """
        Generate results summary for completed assessment.
        
        Args:
            assessment_id: Assessment ID
            
        Returns:
            Results summary data
        """
        assessment = self.storage.assessments.get(assessment_id)
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} not found")
        
        if not assessment.completed_at:
            raise ValueError(f"Assessment {assessment_id} not completed")
        
        # Get user profile
        user = self.storage.get_user(assessment.user_id)
        if not user:
            raise ValueError(f"User {assessment.user_id} not found")
        
        # Generate encouraging message
        encouraging_message = self._generate_encouraging_message(
            assessment.confidence_score,
            assessment.learning_level
        )
        
        # Generate skill breakdown
        skill_breakdown = self._generate_skill_breakdown(assessment)
        
        # Generate next steps
        next_steps = self._generate_next_steps(assessment.learning_level)
        
        # Generate positive framing
        positive_framing = self._generate_positive_framing(assessment)
        
        summary = {
            'assessment_id': assessment_id,
            'user_id': assessment.user_id,
            'display_name': user.display_name,
            'completed_at': assessment.completed_at.isoformat(),
            'learning_level': {
                'level': assessment.learning_level.value,
                'label': self._get_level_label(assessment.learning_level)
            },
            'confidence_score': {
                'score': assessment.confidence_score,
                'display': f"{assessment.confidence_score:.1f}/100",
                'message': encouraging_message
            },
            'skill_breakdown': skill_breakdown,
            'positive_framing': positive_framing,
            'next_steps': next_steps,
            'is_flagged': assessment.is_flagged,
            'flag_reason': assessment.flag_reason
        }
        
        logger.info(f"Results summary generated for assessment {assessment_id}")
        return summary
    
    def _generate_encouraging_message(self, confidence_score: float, learning_level: LearningLevel) -> str:
        """
        Generate encouraging message based on score and level.
        
        Args:
            confidence_score: Confidence score
            learning_level: Learning level
            
        Returns:
            Encouraging message
        """
        if confidence_score >= 80:
            messages = [
                "Excellent start! You have strong communication foundations to build upon.",
                "Great job! Your confidence is high - let's maintain this momentum.",
                "Wonderful! You're showing advanced communication skills already."
            ]
        elif confidence_score >= 60:
            messages = [
                "Good start! You have solid fundamentals with room to grow.",
                "Well done! Your communication skills are developing nicely.",
                "Nice work! You're on a great path to improvement."
            ]
        elif confidence_score >= 40:
            messages = [
                "Welcome! This is your starting point - every expert was once a beginner.",
                "Great first step! You've begun your journey to better communication.",
                "Perfect place to start! Let's build your confidence together."
            ]
        else:
            messages = [
                "Welcome! This assessment helps us understand where to begin your journey.",
                "Great that you're here! Let's work together to build your confidence.",
                "Starting point established! Every improvement journey begins somewhere."
            ]
        
        return messages[hash(learning_level.value) % len(messages)]
    
    def _generate_skill_breakdown(self, assessment: BaselineAssessment) -> Dict:
        """
        Generate skill breakdown with positive framing.
        
        Args:
            assessment: Assessment data
            
        Returns:
            Skill breakdown
        """
        breakdown = {
            'fluency': {
                'score': assessment.fluency_score,
                'display': f"{assessment.fluency_score:.1f}/100",
                'label': 'Fluency',
                'description': self._get_skill_description('fluency', assessment.fluency_score),
                'strength': self._get_skill_strength(assessment.fluency_score)
            },
            'vocabulary': {
                'score': assessment.vocabulary_score,
                'display': f"{assessment.vocabulary_score:.1f}/100",
                'label': 'Vocabulary',
                'description': self._get_skill_description('vocabulary', assessment.vocabulary_score),
                'strength': self._get_skill_strength(assessment.vocabulary_score)
            }
        }
        
        if assessment.pronunciation_score is not None:
            breakdown['pronunciation'] = {
                'score': assessment.pronunciation_score,
                'display': f"{assessment.pronunciation_score:.1f}/100",
                'label': 'Pronunciation',
                'description': self._get_skill_description('pronunciation', assessment.pronunciation_score),
                'strength': self._get_skill_strength(assessment.pronunciation_score)
            }
        
        return breakdown
    
    def _get_skill_description(self, skill: str, score: float) -> str:
        """Get positive description for skill score."""
        descriptions = {
            'fluency': {
                'high': 'You speak with natural flow and good pacing.',
                'medium': 'You show developing flow in your speech patterns.',
                'developing': 'Building your natural speaking rhythm.'
            },
            'vocabulary': {
                'high': 'You use varied and appropriate vocabulary effectively.',
                'medium': 'You have a good foundation with room to expand.',
                'developing': 'Building your word choice variety.'
            },
            'pronunciation': {
                'high': 'Your pronunciation is clear and accurate.',
                'medium': 'Your pronunciation is generally clear with some areas to refine.',
                'developing': 'Working on clarity and accuracy in pronunciation.'
            }
        }
        
        if score >= 70:
            return descriptions[skill]['high']
        elif score >= 50:
            return descriptions[skill]['medium']
        else:
            return descriptions[skill]['developing']
    
    def _get_skill_strength(self, score: float) -> str:
        """Get strength category for skill score."""
        if score >= 70:
            return 'strong'
        elif score >= 50:
            return 'developing'
        else:
            return 'emerging'
    
    def _generate_positive_framing(self, assessment: BaselineAssessment) -> Dict:
        """
        Generate positive framing of the assessment results.
        
        Args:
            assessment: Assessment data
            
        Returns:
            Positive framing data
        """
        return {
            'title': 'Your Communication Journey Starts Here',
            'subtitle': f"Starting Level: {self._get_level_label(assessment.learning_level)}",
            'message': (
                f"This isn't a grade - it's your personalized starting point. "
                f"Your confidence score of {assessment.confidence_score:.1f} shows where you are now, "
                f"and every practice session will help you improve from here."
            ),
            'highlight': self._get_positive_highlight(assessment)
        }
    
    def _get_positive_highlight(self, assessment: BaselineAssessment) -> str:
        """Get positive highlight based on assessment."""
        highlights = []
        
        if assessment.fluency_score >= 70:
            highlights.append("strong natural speaking flow")
        if assessment.vocabulary_score >= 70:
            highlights.append("good vocabulary range")
        if assessment.pronunciation_score and assessment.pronunciation_score >= 70:
            highlights.append("clear pronunciation")
        
        if highlights:
            return f"You show {', '.join(highlights)} - great foundation to build on!"
        else:
            return "You've taken the first step - consistency will lead to improvement."
    
    def _generate_next_steps(self, learning_level: LearningLevel) -> list:
        """
        Generate personalized next steps based on learning level.
        
        Args:
            learning_level: Learning level
            
        Returns:
            List of next steps
        """
        next_steps_map = {
            LearningLevel.BEGINNER: [
                "Start with daily 5-minute practice sessions",
                "Focus on comfortable, everyday conversation topics",
                "Use the AI Conversation Practice for low-pressure learning"
            ],
            LearningLevel.ELEMENTARY: [
                "Practice common workplace and daily life scenarios",
                "Work on expanding your vocabulary range",
                "Try Scenario-Based Learning for real-world context"
            ],
            LearningLevel.INTERMEDIATE: [
                "Challenge yourself with technical and professional topics",
                "Focus on refining your fluency and natural flow",
                "Practice mock interviews for career development"
            ],
            LearningLevel.UPPER_INTERMEDIATE: [
                "Engage with complex topics and abstract discussions",
                "Work on nuance and sophisticated expression",
                "Practice advanced scenarios and negotiations"
            ],
            LearningLevel.ADVANCED: [
                "Focus on specialized vocabulary for your field",
                "Practice high-stakes communication scenarios",
                "Work on subtle aspects of tone and style"
            ],
            LearningLevel.PROFICIENT: [
                "Maintain and refine your advanced skills",
                "Practice complex, multi-participant discussions",
                "Focus on communication leadership and mentoring"
            ]
        }
        
        return next_steps_map.get(learning_level, next_steps_map[LearningLevel.BEGINNER])
    
    def _get_level_label(self, level: LearningLevel) -> str:
        """Get user-friendly label for learning level."""
        labels = {
            LearningLevel.BEGINNER: "Foundational",
            LearningLevel.ELEMENTARY: "Developing",
            LearningLevel.INTERMEDIATE: "Progressing",
            LearningLevel.UPPER_INTERMEDIATE: "Advanced",
            LearningLevel.ADVANCED: "Proficient",
            LearningLevel.PROFICIENT: "Expert"
        }
        return labels.get(level, "Developing")

    def _level_rank(self, level: LearningLevel) -> int:
        """Get ordinal rank of a learning level (low to high), since enum .value strings don't sort correctly."""
        return list(LearningLevel).index(level)

    def generate_progress_comparison(self, user_id: str) -> Optional[Dict]:
        """
        Generate progress comparison if user has multiple assessments.
        
        Args:
            user_id: User ID
            
        Returns:
            Progress comparison data or None if only one assessment
        """
        assessments = self.storage.get_user_assessments(user_id)
        
        if len(assessments) < 2:
            return None
        
        # Get first and latest assessments
        first_assessment = assessments[0]
        latest_assessment = assessments[-1]
        
        if not first_assessment.completed_at or not latest_assessment.completed_at:
            return None
        
        # Calculate improvements
        confidence_change = latest_assessment.confidence_score - first_assessment.confidence_score
        fluency_change = latest_assessment.fluency_score - first_assessment.fluency_score
        vocabulary_change = latest_assessment.vocabulary_score - first_assessment.vocabulary_score
        
        # Calculate days between assessments
        days_between = (latest_assessment.completed_at - first_assessment.completed_at).days
        
        return {
            'days_between': days_between,
            'assessment_count': len(assessments),
            'improvements': {
                'confidence': {
                    'change': confidence_change,
                    'display': f"+{confidence_change:.1f}" if confidence_change > 0 else f"{confidence_change:.1f}",
                    'positive': confidence_change > 0
                },
                'fluency': {
                    'change': fluency_change,
                    'display': f"+{fluency_change:.1f}" if fluency_change > 0 else f"{fluency_change:.1f}",
                    'positive': fluency_change > 0
                },
                'vocabulary': {
                    'change': vocabulary_change,
                    'display': f"+{vocabulary_change:.1f}" if vocabulary_change > 0 else f"{vocabulary_change:.1f}",
                    'positive': vocabulary_change > 0
                }
            },
            'level_progression': {
                'from': self._get_level_label(first_assessment.learning_level),
                'to': self._get_level_label(latest_assessment.learning_level),
                'improved': self._level_rank(latest_assessment.learning_level) > self._level_rank(first_assessment.learning_level)
            }
        }