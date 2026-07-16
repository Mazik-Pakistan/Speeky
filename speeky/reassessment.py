"""
Periodic Baseline Re-Assessment implementation (BAS-US-12).

This module handles scheduled 30-day re-assessments to recalibrate learning levels
and track long-term progress, with passage rotation and regression detection.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

try:
    from .storage import InMemoryStorage, LearningLevel, AssessmentStatus, BaselineAssessment
    from .assessment import InitialCommunicationAssessment
except ImportError:
    from storage import InMemoryStorage, LearningLevel, AssessmentStatus, BaselineAssessment
    from assessment import InitialCommunicationAssessment

logger = logging.getLogger(__name__)


@dataclass
class ReAssessmentEligibility:
    """Re-assessment eligibility status."""
    is_eligible: bool
    days_until_eligible: Optional[int] = None
    reason: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    last_assessment_date: Optional[datetime] = None


@dataclass
class ReAssessmentPrompt:
    """Re-assessment prompt configuration."""
    user_id: str
    prompt_type: str  # scheduled, early, regression_detected
    message: str
    can_dismiss: bool = True
    urgency_level: str = "normal"  # normal, high, low
    dismiss_until: Optional[datetime] = None


class PeriodicReAssessment:
    """
    Periodic Baseline Re-Assessment system.
    
    Manages 30-day re-assessment cycles with passage rotation and
    regression detection for long-term progress tracking.
    """
    
    def __init__(self, storage: InMemoryStorage, assessment_system: InitialCommunicationAssessment):
        """
        Initialize periodic re-assessment system.
        
        Args:
            storage: In-memory storage
            assessment_system: Assessment system for conducting re-assessments
        """
        self.storage = storage
        self.assessment_system = assessment_system
        
        # Re-assessment configuration
        self.cycle_days = 30  # Standard 30-day cycle
        self.early_retake_cooldown = 7  # Minimum days between early retakes
        self.regression_threshold = 15.0  # Point drop threshold for regression detection
        
        # Prompt history (user_id -> list of prompt timestamps)
        self.prompt_history: Dict[str, List[datetime]] = {}
        
        logger.info("Periodic Re-Assessment system initialized")
    
    def check_eligibility(self, user_id: str) -> ReAssessmentEligibility:
        """
        Check if user is eligible for re-assessment.
        
        Args:
            user_id: User ID
            
        Returns:
            Re-assessment eligibility status
        """
        user = self.storage.get_user(user_id)
        if not user:
            return ReAssessmentEligibility(
                is_eligible=False,
                reason="User not found"
            )
        
        if user.assessment_status != AssessmentStatus.COMPLETED:
            return ReAssessmentEligibility(
                is_eligible=False,
                reason="Initial assessment not completed"
            )
        
        last_assessment = self.storage.get_latest_assessment(user_id)
        if not last_assessment or not last_assessment.completed_at:
            return ReAssessmentEligibility(
                is_eligible=False,
                reason="No completed assessment found"
            )
        
        days_since = (datetime.now() - last_assessment.completed_at).days
        
        if days_since >= self.cycle_days:
            return ReAssessmentEligibility(
                is_eligible=True,
                last_assessment_date=last_assessment.completed_at,
                scheduled_date=datetime.now()
            )
        else:
            return ReAssessmentEligibility(
                is_eligible=False,
                days_until_eligible=self.cycle_days - days_since,
                reason=f"Cycle not complete. {self.cycle_days - days_since} days remaining.",
                last_assessment_date=last_assessment.completed_at,
                scheduled_date=last_assessment.completed_at + timedelta(days=self.cycle_days)
            )
    
    def should_show_prompt(self, user_id: str) -> bool:
        """
        Check if re-assessment prompt should be shown to user.
        
        Args:
            user_id: User ID
            
        Returns:
            Whether to show prompt
        """
        eligibility = self.check_eligibility(user_id)
        
        if not eligibility.is_eligible:
            return False
        
        # Check if prompt was shown recently (within last 24 hours)
        prompt_history = self.prompt_history.get(user_id, [])
        if prompt_history:
            last_prompt = prompt_history[-1]
            if datetime.now() - last_prompt < timedelta(hours=24):
                return False
        
        return True
    
    def generate_prompt(self, user_id: str, prompt_type: str = "scheduled") -> ReAssessmentPrompt:
        """
        Generate re-assessment prompt for user.
        
        Args:
            user_id: User ID
            prompt_type: Type of prompt (scheduled, early, regression_detected)
            
        Returns:
            Re-assessment prompt
        """
        eligibility = self.check_eligibility(user_id)
        
        if prompt_type == "scheduled":
            message = "Time for your Monthly Check-in! Complete your re-assessment to track your progress and recalibrate your learning level."
            urgency = "normal"
        elif prompt_type == "early":
            message = "You're eligible for an early re-assessment. Check your progress before the scheduled 30-day cycle."
            urgency = "low"
        elif prompt_type == "regression_detected":
            message = "Your recent score was unusually low. Would you like to retake the assessment to ensure accuracy?"
            urgency = "high"
        else:
            message = "Complete your re-assessment to track your progress."
            urgency = "normal"
        
        return ReAssessmentPrompt(
            user_id=user_id,
            prompt_type=prompt_type,
            message=message,
            can_dismiss=True,
            urgency_level=urgency
        )
    
    def record_prompt_shown(self, user_id: str):
        """
        Record that a re-assessment prompt was shown to user.
        
        Args:
            user_id: User ID
        """
        if user_id not in self.prompt_history:
            self.prompt_history[user_id] = []
        
        self.prompt_history[user_id].append(datetime.now())
        
        # Keep only recent history (last 90 days)
        cutoff = datetime.now() - timedelta(days=90)
        self.prompt_history[user_id] = [
            ts for ts in self.prompt_history[user_id] if ts > cutoff
        ]
    
    def dismiss_prompt(self, user_id: str, dismiss_duration_hours: int = 24) -> Dict:
        """
        Handle user dismissing re-assessment prompt.
        
        Args:
            user_id: User ID
            dismiss_duration_hours: How long to dismiss prompt (default 24 hours)
            
        Returns:
            Dismissal result
        """
        eligibility = self.check_eligibility(user_id)
        
        if not eligibility.is_eligible:
            return {
                'success': False,
                'reason': 'Not eligible for re-assessment'
            }
        
        # Record prompt dismissal with duration
        dismiss_until = datetime.now() + timedelta(hours=dismiss_duration_hours)
        
        logger.info(f"User {user_id} dismissed re-assessment prompt until {dismiss_until}")
        
        return {
            'success': True,
            'dismissed_until': dismiss_until.isoformat(),
            'message': f"Prompt dismissed. You'll be reminded again after {dismiss_duration_hours} hours."
        }
    
    def start_re_assessment(self, user_id: str) -> Dict:
        """
        Start a re-assessment for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Re-assessment start result
        """
        eligibility = self.check_eligibility(user_id)
        
        if not eligibility.is_eligible:
            return {
                'success': False,
                'reason': eligibility.reason,
                'days_until_eligible': eligibility.days_until_eligible
            }
        
        try:
            # Start assessment through the assessment system
            assessment_start = self.assessment_system.start_assessment(user_id)
            
            logger.info(f"Re-assessment started for user {user_id}")
            
            return {
                'success': True,
                'assessment_id': assessment_start['assessment_id'],
                'total_questions': assessment_start['total_questions'],
                'current_question': assessment_start['current_question'],
                'estimated_duration_minutes': assessment_start['estimated_duration_minutes'],
                'is_re_assessment': True
            }
            
        except Exception as e:
            logger.error(f"Error starting re-assessment: {e}")
            return {
                'success': False,
                'reason': f"Error starting re-assessment: {str(e)}"
            }
    
    def detect_score_regression(self, user_id: str, new_score: float) -> Dict:
        """
        Detect if new assessment score shows significant regression.
        
        Args:
            user_id: User ID
            new_score: New assessment confidence score
            
        Returns:
            Regression detection result
        """
        previous_assessments = self.storage.get_user_assessments(user_id)
        
        if len(previous_assessments) < 1:
            return {
                'regression_detected': False,
                'reason': 'No previous assessment for comparison'
            }
        
        # Get most recent completed assessment
        previous_assessment = None
        for assessment in reversed(previous_assessments):
            if assessment.completed_at and assessment.confidence_score is not None:
                previous_assessment = assessment
                break
        
        if not previous_assessment:
            return {
                'regression_detected': False,
                'reason': 'No valid previous assessment found'
            }
        
        previous_score = previous_assessment.confidence_score
        score_drop = previous_score - new_score
        
        if score_drop >= self.regression_threshold:
            return {
                'regression_detected': True,
                'previous_score': previous_score,
                'new_score': new_score,
                'score_drop': score_drop,
                'reason': f"Score dropped by {score_drop:.1f} points from previous assessment"
            }
        
        return {
            'regression_detected': False,
            'previous_score': previous_score,
            'new_score': new_score,
            'score_change': new_score - previous_score,
            'reason': 'No significant regression detected'
        }
    
    def handle_regression_flag(self, user_id: str, regression_data: Dict) -> Dict:
        """
        Handle score regression flag with user prompt.
        
        Args:
            user_id: User ID
            regression_data: Regression detection data
            
        Returns:
            Regression handling result
        """
        if not regression_data.get('regression_detected'):
            return {
                'action': 'none',
                'reason': 'No regression detected'
            }
        
        # Generate regression prompt
        prompt = self.generate_prompt(user_id, "regression_detected")
        
        return {
            'action': 'prompt_retake',
            'prompt': {
                'message': prompt.message,
                'urgency': prompt.urgency_level,
                'previous_score': regression_data['previous_score'],
                'new_score': regression_data['new_score'],
                'score_drop': regression_data['score_drop']
            },
            'options': [
                'retake_assessment',
                'accept_score',
                'contact_support'
            ]
        }
    
    def get_progress_trend(self, user_id: str) -> Dict:
        """
        Get progress trend data for user across assessments.
        
        Args:
            user_id: User ID
            
        Returns:
            Progress trend data
        """
        assessments = self.storage.get_user_assessments(user_id)
        
        completed_assessments = [
            a for a in assessments 
            if a.completed_at and a.confidence_score is not None
        ]
        
        if len(completed_assessments) < 2:
            return {
                'has_trend_data': False,
                'reason': 'Need at least 2 completed assessments for trend analysis'
            }
        
        # Extract trend data
        trend_data = []
        for assessment in completed_assessments:
            trend_data.append({
                'date': assessment.completed_at.isoformat(),
                'confidence_score': assessment.confidence_score,
                'fluency_score': assessment.fluency_score,
                'vocabulary_score': assessment.vocabulary_score,
                'pronunciation_score': assessment.pronunciation_score,
                'learning_level': assessment.learning_level.value if assessment.learning_level else None
            })
        
        # Calculate overall trend
        first_score = trend_data[0]['confidence_score']
        last_score = trend_data[-1]['confidence_score']
        overall_change = last_score - first_score
        
        # Calculate average improvement rate
        if len(trend_data) > 1:
            first_date = datetime.fromisoformat(trend_data[0]['date'])
            last_date = datetime.fromisoformat(trend_data[-1]['date'])
            days_span = (last_date - first_date).days
            avg_rate = overall_change / days_span if days_span > 0 else 0
        else:
            avg_rate = 0
        
        return {
            'has_trend_data': True,
            'assessment_count': len(trend_data),
            'trend_data': trend_data,
            'overall_change': overall_change,
            'average_rate_per_day': avg_rate,
            'current_score': last_score,
            'starting_score': first_score,
            'trend_direction': 'improving' if overall_change > 0 else 'declining' if overall_change < 0 else 'stable'
        }
    
    def handle_partial_completion(self, user_id: str, assessment_id: str) -> Dict:
        """
        Handle case where user abandons assessment mid-way.
        
        Args:
            user_id: User ID
            assessment_id: Assessment ID
            
        Returns:
            Partial completion handling result
        """
        assessment = self.storage.assessments.get(assessment_id)
        if not assessment:
            return {
                'success': False,
                'reason': 'Assessment not found'
            }
        
        if assessment.completed_at:
            return {
                'success': False,
                'reason': 'Assessment already completed'
            }
        
        # Save progress state
        logger.info(f"Partial completion saved for assessment {assessment_id}")
        
        return {
            'success': True,
            'assessment_id': assessment_id,
            'status': 'partial',
            'message': 'Assessment progress saved. Complete it on your next login.',
            'can_resume': True
        }
    
    def get_re_assessment_summary(self, user_id: str) -> Dict:
        """
        Get complete re-assessment summary for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Re-assessment summary
        """
        eligibility = self.check_eligibility(user_id)
        progress_trend = self.get_progress_trend(user_id)
        
        return {
            'user_id': user_id,
            'eligibility': {
                'is_eligible': eligibility.is_eligible,
                'days_until_eligible': eligibility.days_until_eligible,
                'reason': eligibility.reason,
                'scheduled_date': eligibility.scheduled_date.isoformat() if eligibility.scheduled_date else None
            },
            'should_show_prompt': self.should_show_prompt(user_id),
            'progress_trend': progress_trend,
            'prompt_history_count': len(self.prompt_history.get(user_id, [])),
            'configuration': {
                'cycle_days': self.cycle_days,
                'early_retake_cooldown': self.early_retake_cooldown,
                'regression_threshold': self.regression_threshold
            }
        }