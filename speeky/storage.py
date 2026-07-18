"""
In-memory storage system for Baseline Assessment feature.

This module provides temporary storage for user profiles, baseline assessments,
and session history without requiring a database.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class AssessmentStatus(Enum):
    """Status of baseline assessment."""
    UNASSESSED = "unassessed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PLATEAUED = "plateaued"


class LearningLevel(Enum):
    """Learning levels based on confidence score."""
    BEGINNER = "beginner"
    ELEMENTARY = "elementary"
    INTERMEDIATE = "intermediate"
    UPPER_INTERMEDIATE = "upper_intermediate"
    ADVANCED = "advanced"
    PROFICIENT = "proficient"


@dataclass
class UserProfile:
    """User profile data."""
    user_id: str
    external_id: str  # From external auth system
    display_name: str
    created_at: datetime = field(default_factory=datetime.now)
    assessment_status: AssessmentStatus = AssessmentStatus.UNASSESSED
    learning_level: Optional[LearningLevel] = None
    learning_goals: List[str] = field(default_factory=list)
    is_enterprise: bool = False
    organization_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'user_id': self.user_id,
            'external_id': self.external_id,
            'display_name': self.display_name,
            'created_at': self.created_at.isoformat(),
            'assessment_status': self.assessment_status.value,
            'learning_level': self.learning_level.value if self.learning_level else None,
            'learning_goals': self.learning_goals,
            'is_enterprise': self.is_enterprise,
            'organization_id': self.organization_id
        }


@dataclass
class BaselineAssessment:
    """Baseline assessment data."""
    assessment_id: str
    user_id: str
    completed_at: Optional[datetime] = None
    fluency_score: Optional[float] = None
    vocabulary_score: Optional[float] = None
    pronunciation_score: Optional[float] = None
    confidence_score: Optional[float] = None
    learning_level: Optional[LearningLevel] = None
    passage_id: Optional[str] = None
    is_flagged: bool = False
    flag_reason: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'assessment_id': self.assessment_id,
            'user_id': self.user_id,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'fluency_score': self.fluency_score,
            'vocabulary_score': self.vocabulary_score,
            'pronunciation_score': self.pronunciation_score,
            'confidence_score': self.confidence_score,
            'learning_level': self.learning_level.value if self.learning_level else None,
            'passage_id': self.passage_id,
            'is_flagged': self.is_flagged,
            'flag_reason': self.flag_reason
        }


@dataclass
class ReAssessmentRequest:
    """Re-assessment request tracking."""
    request_id: str
    user_id: str
    requested_at: datetime
    scheduled_date: Optional[datetime] = None
    completed: bool = False
    is_early_retake: bool = False
    cycle_count: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'request_id': self.request_id,
            'user_id': self.user_id,
            'requested_at': self.requested_at.isoformat(),
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'completed': self.completed,
            'is_early_retake': self.is_early_retake,
            'cycle_count': self.cycle_count
        }


class InMemoryStorage:
    """
    In-memory storage for Baseline Assessment data.
    
    Provides temporary storage without database persistence.
    All data is lost when the application restarts.
    """
    
    def __init__(self):
        """Initialize in-memory storage."""
        self.users: Dict[str, UserProfile] = {}
        self.assessments: Dict[str, BaselineAssessment] = {}
        self.user_assessments: Dict[str, List[str]] = {}  # user_id -> [assessment_ids]
        self.reassessment_requests: Dict[str, ReAssessmentRequest] = {}
        self.user_reassessments: Dict[str, List[str]] = {}  # user_id -> [request_ids]
        self.assessment_passages: List[str] = [
            "baseline_passage_1",
            "baseline_passage_2", 
            "baseline_passage_3",
            "baseline_passage_4",
            "baseline_passage_5"
        ]
        self.current_assessments: Dict[str, Dict] = {}  # user_id -> current assessment state
        
        logger.info("In-memory storage initialized")
    
    def create_user(self, external_id: str, display_name: str, 
                    is_enterprise: bool = False, organization_id: Optional[str] = None) -> UserProfile:
        """
        Create a new user profile.
        
        Args:
            external_id: External system user ID
            display_name: User's display name
            is_enterprise: Whether user is from enterprise organization
            organization_id: Organization ID for enterprise users
            
        Returns:
            Created user profile
        """
        user_id = str(uuid.uuid4())
        user = UserProfile(
            user_id=user_id,
            external_id=external_id,
            display_name=display_name,
            is_enterprise=is_enterprise,
            organization_id=organization_id
        )
        
        self.users[user_id] = user
        self.user_assessments[user_id] = []
        self.user_reassessments[user_id] = []
        
        logger.info(f"User created: {user_id} (external: {external_id})")
        return user
    
    def get_user_by_external_id(self, external_id: str) -> Optional[UserProfile]:
        """Get user by external ID."""
        for user in self.users.values():
            if user.external_id == external_id:
                return user
        return None
    
    def get_user(self, user_id: str) -> Optional[UserProfile]:
        """Get user by internal ID."""
        return self.users.get(user_id)
    
    def update_user_assessment_status(self, user_id: str, status: AssessmentStatus):
        """Update user's assessment status."""
        user = self.get_user(user_id)
        if user:
            user.assessment_status = status
            logger.info(f"User {user_id} assessment status updated to {status.value}")
    
    def update_user_learning_level(self, user_id: str, level: LearningLevel):
        """Update user's learning level."""
        user = self.get_user(user_id)
        if user:
            user.learning_level = level
            logger.info(f"User {user_id} learning level updated to {level.value}")
    
    def create_baseline_assessment(self, user_id: str) -> BaselineAssessment:
        """
        Create a new baseline assessment.
        
        Args:
            user_id: User ID
            
        Returns:
            Created assessment
        """
        assessment_id = str(uuid.uuid4())
        
        # Clear any existing current assessment state
        self.clear_current_assessment(user_id)
        
        # Get passage that wasn't used in last assessment
        user_assessment_ids = self.user_assessments.get(user_id, [])
        last_passage_id = None
        if user_assessment_ids:
            last_assessment = self.assessments.get(user_assessment_ids[-1])
            if last_assessment:
                last_passage_id = last_assessment.passage_id
        
        # Select new passage
        available_passages = [p for p in self.assessment_passages if p != last_passage_id]
        passage_id = available_passages[0] if available_passages else self.assessment_passages[0]
        
        assessment = BaselineAssessment(
            assessment_id=assessment_id,
            user_id=user_id,
            passage_id=passage_id
        )
        
        self.assessments[assessment_id] = assessment
        self.user_assessments[user_id].append(assessment_id)
        
        # Update user status to in_progress
        self.update_user_assessment_status(user_id, AssessmentStatus.IN_PROGRESS)
        
        logger.info(f"Baseline assessment created: {assessment_id} for user {user_id}")
        return assessment
    
    def complete_baseline_assessment(self, assessment_id: str, 
                                   fluency_score: float,
                                   vocabulary_score: float,
                                   pronunciation_score: Optional[float],
                                   confidence_score: float,
                                   learning_level: LearningLevel) -> BaselineAssessment:
        """
        Complete a baseline assessment with scores.
        
        Args:
            assessment_id: Assessment ID
            fluency_score: Fluency score (0-100)
            vocabulary_score: Vocabulary score (0-100)
            pronunciation_score: Pronunciation score (0-100) or None for text-only
            confidence_score: Overall confidence score (0-100)
            learning_level: Assigned learning level
            
        Returns:
            Updated assessment
        """
        assessment = self.assessments.get(assessment_id)
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} not found")
        
        assessment.completed_at = datetime.now()
        assessment.fluency_score = fluency_score
        assessment.vocabulary_score = vocabulary_score
        assessment.pronunciation_score = pronunciation_score
        assessment.confidence_score = confidence_score
        assessment.learning_level = learning_level
        
        # Update user status and level
        self.update_user_assessment_status(assessment.user_id, AssessmentStatus.COMPLETED)
        self.update_user_learning_level(assessment.user_id, learning_level)
        
        logger.info(f"Baseline assessment completed: {assessment_id}")
        return assessment
    
    def flag_assessment(self, assessment_id: str, reason: str):
        """
        Flag an assessment for integrity issues.
        
        Args:
            assessment_id: Assessment ID
            reason: Reason for flagging
        """
        assessment = self.assessments.get(assessment_id)
        if assessment:
            assessment.is_flagged = True
            assessment.flag_reason = reason
            logger.warning(f"Assessment {assessment_id} flagged: {reason}")
    
    def get_user_assessments(self, user_id: str) -> List[BaselineAssessment]:
        """Get all assessments for a user."""
        assessment_ids = self.user_assessments.get(user_id, [])
        return [self.assessments[aid] for aid in assessment_ids if aid in self.assessments]
    
    def get_latest_assessment(self, user_id: str) -> Optional[BaselineAssessment]:
        """Get the most recent assessment for a user."""
        assessments = self.get_user_assessments(user_id)
        if assessments:
            return assessments[-1]
        return None
    
    def request_reassessment(self, user_id: str, is_early: bool = False) -> ReAssessmentRequest:
        """
        Request a re-assessment for a user.
        
        Args:
            user_id: User ID
            is_early: Whether this is an early voluntary retake
            
        Returns:
            Re-assessment request
        """
        request_id = str(uuid.uuid4())

        # Check eligibility
        last_assessment = self.get_latest_assessment(user_id)
        current_cycle = self._get_current_cycle_number(user_id)
        scheduled_date = None

        if last_assessment and last_assessment.completed_at:
            # Calculate days since last assessment
            days_since = (datetime.now() - last_assessment.completed_at).days

            # Count previous early retakes already used in the current cycle
            user_requests = self.user_reassessments.get(user_id, [])
            early_requests_this_cycle = sum(
                1 for rid in user_requests
                if self.reassessment_requests[rid].is_early_retake
                and self.reassessment_requests[rid].cycle_count == current_cycle
            )

            if is_early:
                # Early retake: schedule immediately if eligible
                if days_since < 7:
                    raise ValueError(f"Early retake not eligible. {7 - days_since} days remaining.")
                if early_requests_this_cycle >= 1:
                    raise ValueError("Already used early retake for this cycle.")
            else:
                # Scheduled 30-day re-assessment
                if days_since < 30:
                    scheduled_date = last_assessment.completed_at + timedelta(days=30)
                else:
                    scheduled_date = datetime.now()

        request = ReAssessmentRequest(
            request_id=request_id,
            user_id=user_id,
            requested_at=datetime.now(),
            scheduled_date=scheduled_date,
            is_early_retake=is_early,
            cycle_count=current_cycle
        )
        
        self.reassessment_requests[request_id] = request
        self.user_reassessments[user_id].append(request_id)
        
        logger.info(f"Re-assessment requested: {request_id} for user {user_id}")
        return request
    
    def _get_current_cycle_number(self, user_id: str) -> int:
        """Calculate current 30-day cycle number for user."""
        first_assessment = self.get_user_assessments(user_id)[0] if self.get_user_assessments(user_id) else None
        if not first_assessment or not first_assessment.completed_at:
            return 0
        
        days_since = (datetime.now() - first_assessment.completed_at).days
        return days_since // 30 + 1
    
    def complete_reassessment(self, request_id: str, assessment_id: str):
        """Mark a re-assessment request as completed."""
        request = self.reassessment_requests.get(request_id)
        if request:
            request.completed = True
            logger.info(f"Re-assessment completed: {request_id}")
    
    def get_user_reassessments(self, user_id: str) -> List[ReAssessmentRequest]:
        """Get all re-assessment requests for a user."""
        request_ids = self.user_reassessments.get(user_id, [])
        return [self.reassessment_requests[rid] for rid in request_ids if rid in self.reassessment_requests]
    
    def check_stagnation(self, user_id: str, min_cycles: int = 3) -> bool:
        """
        Check if user's confidence score has plateaued.
        
        Args:
            user_id: User ID
            min_cycles: Minimum number of cycles required
            
        Returns:
            True if plateaued
        """
        assessments = self.get_user_assessments(user_id)
        
        if len(assessments) < min_cycles:
            return False
        
        # Get last 3 assessments
        recent_assessments = assessments[-min_cycles:]
        scores = [a.confidence_score for a in recent_assessments if a.confidence_score is not None]
        
        if len(scores) < min_cycles:
            return False
        
        # Check if variance is below threshold
        variance = max(scores) - min(scores)
        is_plateaued = variance < 5.0  # Less than 5 point variance
        
        if is_plateaued:
            user = self.get_user(user_id)
            if user:
                user.assessment_status = AssessmentStatus.PLATEAUED
                logger.info(f"User {user_id} detected as plateaued")
        
        return is_plateaued
    
    def set_current_assessment(self, user_id: str, assessment_data: Dict):
        """Store current assessment state for a user."""
        self.current_assessments[user_id] = assessment_data
        logger.info(f"Current assessment state stored for user {user_id}")
    
    def get_current_assessment(self, user_id: str) -> Optional[Dict]:
        """Get current assessment state for a user."""
        return self.current_assessments.get(user_id)
    
    def clear_current_assessment(self, user_id: str):
        """Clear current assessment state for a user."""
        if user_id in self.current_assessments:
            del self.current_assessments[user_id]
            logger.info(f"Current assessment state cleared for user {user_id}")
    
    def get_storage_stats(self) -> Dict:
        """Get storage statistics."""
        return {
            'total_users': len(self.users),
            'total_assessments': len(self.assessments),
            'total_reassessment_requests': len(self.reassessment_requests),
            'assessed_users': sum(1 for u in self.users.values() 
                                if u.assessment_status == AssessmentStatus.COMPLETED),
            'unassessed_users': sum(1 for u in self.users.values() 
                                  if u.assessment_status == AssessmentStatus.UNASSESSED)
        }
    
    def clear_all_data(self):
        """Clear all stored data (for testing)."""
        self.users.clear()
        self.assessments.clear()
        self.user_assessments.clear()
        self.reassessment_requests.clear()
        self.user_reassessments.clear()
        logger.warning("All in-memory data cleared")