"""
Skip Assessment & Feature-Access Gating implementation (BAS-US-02).

This module manages feature access control based on assessment completion status,
ensuring users complete baseline assessment before accessing coaching features.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum

try:
    from .storage import InMemoryStorage, AssessmentStatus, UserProfile
except ImportError:
    from storage import InMemoryStorage, AssessmentStatus, UserProfile

logger = logging.getLogger(__name__)


class FeatureAccessLevel(Enum):
    """Feature access levels based on assessment status."""
    FULL_ACCESS = "full_access"
    ASSESSMENT_REQUIRED = "assessment_required"
    BASIC_ONLY = "basic_only"


class GatedFeature(Enum):
    """Features that require assessment completion."""
    AI_CONVERSATION_PRACTICE = "ai_conversation_practice"
    INTERVIEW_COACH = "interview_coach"
    SCENARIO_BASED_LEARNING = "scenario_based_learning"
    PROGRESS_DASHBOARD = "progress_dashboard"
    LEARNING_PATHS = "learning_paths"
    DAILY_CHALLENGES = "daily_challenges"
    MOCK_INTERVIEWS = "mock_interviews"


class BasicFeature(Enum):
    """Features available without assessment."""
    ACCOUNT_SETTINGS = "account_settings"
    PROFILE_MANAGEMENT = "profile_management"
    HELP_DOCUMENTATION = "help_documentation"
    ASSESSMENT_INTRO = "assessment_intro"


class FeatureAccessGating:
    """
    Feature access gating system.
    
    Controls access to coaching features based on assessment completion status.
    """
    
    def __init__(self, storage: InMemoryStorage):
        """
        Initialize feature access gating.
        
        Args:
            storage: In-memory storage
        """
        self.storage = storage
        self.skip_prompt_history: Dict[str, List[datetime]] = {}  # user_id -> prompt timestamps
        
        # Define feature mappings
        self.gated_features = {
            GatedFeature.AI_CONVERSATION_PRACTICE: "AI Conversation Practice",
            GatedFeature.INTERVIEW_COACH: "Interview Coach",
            GatedFeature.SCENARIO_BASED_LEARNING: "Scenario-Based Learning",
            GatedFeature.PROGRESS_DASHBOARD: "Progress Dashboard",
            GatedFeature.LEARNING_PATHS: "Learning Paths",
            GatedFeature.DAILY_CHALLENGES: "Daily Challenges",
            GatedFeature.MOCK_INTERVIEWS: "Mock Interviews"
        }
        
        self.basic_features = {
            BasicFeature.ACCOUNT_SETTINGS: "Account Settings",
            BasicFeature.PROFILE_MANAGEMENT: "Profile Management",
            BasicFeature.HELP_DOCUMENTATION: "Help Documentation",
            BasicFeature.ASSESSMENT_INTRO: "Assessment Introduction"
        }
        
        logger.info("Feature Access Gating initialized")
    
    def get_access_level(self, user_id: str) -> FeatureAccessLevel:
        """
        Get current access level for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Feature access level
        """
        user = self.storage.get_user(user_id)
        if not user:
            return FeatureAccessLevel.ASSESSMENT_REQUIRED
        
        if user.assessment_status == AssessmentStatus.COMPLETED:
            return FeatureAccessLevel.FULL_ACCESS
        elif user.assessment_status == AssessmentStatus.UNASSESSED:
            return FeatureAccessLevel.BASIC_ONLY
        else:
            return FeatureAccessLevel.ASSESSMENT_REQUIRED
    
    def check_feature_access(self, user_id: str, feature: str) -> Dict:
        """
        Check if user can access a specific feature.
        
        Args:
            user_id: User ID
            feature: Feature identifier
            
        Returns:
            Access check result
        """
        access_level = self.get_access_level(user_id)
        
        # Check if it's a basic feature
        try:
            basic_feature = BasicFeature(feature)
            if basic_feature in self.basic_features:
                return {
                    'accessible': True,
                    'feature': feature,
                    'access_level': access_level.value,
                    'reason': 'Basic feature always available'
                }
        except ValueError:
            pass  # Not a basic feature
        
        # Check if it's a gated feature
        try:
            gated_feature = GatedFeature(feature)
            if gated_feature in self.gated_features:
                if access_level == FeatureAccessLevel.FULL_ACCESS:
                    return {
                        'accessible': True,
                        'feature': feature,
                        'access_level': access_level.value,
                        'reason': 'Assessment completed'
                    }
                else:
                    return {
                        'accessible': False,
                        'feature': feature,
                        'access_level': access_level.value,
                        'reason': 'Assessment required to unlock this feature',
                        'feature_name': self.gated_features[gated_feature]
                    }
        except ValueError:
            pass  # Unknown feature
        
        # Default: allow access for unknown features
        return {
            'accessible': True,
            'feature': feature,
            'access_level': access_level.value,
            'reason': 'Unknown feature, allowing access'
        }
    
    def get_accessible_features(self, user_id: str) -> Dict:
        """
        Get all accessible features for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary of accessible and inaccessible features
        """
        access_level = self.get_access_level(user_id)
        
        if access_level == FeatureAccessLevel.FULL_ACCESS:
            return {
                'access_level': access_level.value,
                'accessible_features': [f.value for f in self.gated_features] + [f.value for f in self.basic_features],
                'inaccessible_features': []
            }
        else:
            gated = [f.value for f in self.gated_features]
            basic = [f.value for f in self.basic_features]
            
            return {
                'access_level': access_level.value,
                'accessible_features': basic,
                'inaccessible_features': gated,
                'locked_message': self._get_locked_message(access_level)
            }
    
    def attempt_skip_assessment(self, user_id: str, force: bool = False) -> Dict:
        """
        Handle user attempt to skip assessment.
        
        Args:
            user_id: User ID
            force: Whether to force skip (for testing)
            
        Returns:
            Skip attempt result
        """
        user = self.storage.get_user(user_id)
        if not user:
            return {
                'success': False,
                'reason': 'User not found'
            }
        
        # Check if user is enterprise with mandatory assessment
        if user.is_enterprise and self._check_enterprise_mandatory_policy(user.organization_id):
            return {
                'success': False,
                'reason': 'Enterprise policy requires mandatory assessment',
                'can_skip': False,
                'message': 'Your organization requires completion of the baseline assessment.'
            }
        
        # Check skip prompt history
        prompt_count = self._get_skip_prompt_count(user_id)
        
        if not force and prompt_count >= 3:
            # Escalate messaging for repeated skipping
            return {
                'success': False,
                'reason': 'Repeated skip attempts',
                'can_skip': True,
                'escalated': True,
                'message': (
                    f"You've skipped the assessment {prompt_count} times. "
                    "Without it, you cannot access AI Conversation Practice, Interview Coach, "
                    "or Scenario-Based Learning. Complete the assessment to unlock all features."
                )
            }
        
        # Show skip warning modal
        return {
            'success': True,
            'action_required': 'confirm_skip',
            'can_skip': True,
            'message': (
                "All coaching features require a baseline score to personalize your practice. "
                "Without the assessment, AI Conversation Practice, Interview Coach, and "
                "Scenario-Based Learning will be locked. You can complete the assessment later."
            ),
            'skip_count': prompt_count
        }
    
    def confirm_skip_assessment(self, user_id: str) -> Dict:
        """
        Confirm and process assessment skip.
        
        Args:
            user_id: User ID
            
        Returns:
            Skip confirmation result
        """
        user = self.storage.get_user(user_id)
        if not user:
            return {
                'success': False,
                'reason': 'User not found'
            }
        
        # Update user status to unassessed
        self.storage.update_user_assessment_status(user_id, AssessmentStatus.UNASSESSED)
        
        # Record skip prompt
        self._record_skip_prompt(user_id)
        
        # Clear any in-progress assessment
        existing_assessment = self.storage.get_latest_assessment(user_id)
        if existing_assessment and not existing_assessment.completed_at:
            # Would need to implement assessment deletion logic
            logger.info(f"Discarding incomplete assessment for user {user_id}")
        
        logger.info(f"User {user_id} confirmed assessment skip")
        
        return {
            'success': True,
            'status': 'unassessed',
            'message': 'Assessment skipped. Complete it later to unlock all features.',
            'accessible_features': self.get_accessible_features(user_id)
        }
    
    def should_show_assessment_prompt(self, user_id: str) -> bool:
        """
        Check if assessment prompt should be shown to user.
        
        Args:
            user_id: User ID
            
        Returns:
            Whether to show prompt
        """
        user = self.storage.get_user(user_id)
        if not user:
            return False
        
        # Only show if unassessed
        if user.assessment_status != AssessmentStatus.UNASSESSED:
            return False
        
        # Check if shown in current session
        prompt_history = self.skip_prompt_history.get(user_id, [])
        if not prompt_history:
            return True
        
        # Check if shown in last hour (session duration approximation)
        last_prompt = prompt_history[-1]
        if datetime.now() - last_prompt < timedelta(hours=1):
            return False
        
        return True
    
    def get_assessment_prompt_message(self, user_id: str) -> str:
        """
        Get appropriate assessment prompt message.
        
        Args:
            user_id: User ID
            
        Returns:
            Prompt message
        """
        prompt_count = self._get_skip_prompt_count(user_id)
        
        if prompt_count == 0:
            return "Complete your baseline assessment to unlock personalized learning features."
        elif prompt_count == 1:
            return "Your assessment is still pending. Complete it to access AI Conversation Practice and other features."
        elif prompt_count == 2:
            return "You still haven't completed the assessment. Unlock all features by spending 5 minutes on the baseline evaluation."
        else:
            return f"You've skipped the assessment {prompt_count} times. Complete it now to access the full learning experience."
    
    def _record_skip_prompt(self, user_id: str):
        """Record that skip prompt was shown to user."""
        if user_id not in self.skip_prompt_history:
            self.skip_prompt_history[user_id] = []
        
        self.skip_prompt_history[user_id].append(datetime.now())
        
        # Keep only recent history (last 30 days)
        cutoff = datetime.now() - timedelta(days=30)
        self.skip_prompt_history[user_id] = [
            ts for ts in self.skip_prompt_history[user_id] if ts > cutoff
        ]
    
    def _get_skip_prompt_count(self, user_id: str) -> int:
        """Get count of skip prompts shown to user."""
        return len(self.skip_prompt_history.get(user_id, []))
    
    def _check_enterprise_mandatory_policy(self, organization_id: Optional[str]) -> bool:
        """
        Check if enterprise organization has mandatory assessment policy.
        
        Args:
            organization_id: Organization ID
            
        Returns:
            Whether assessment is mandatory
        """
        # In a real implementation, this would check organization settings
        # For now, return False (assessment not mandatory)
        return False
    
    def _get_locked_message(self, access_level: FeatureAccessLevel) -> str:
        """Get message for locked features."""
        if access_level == FeatureAccessLevel.BASIC_ONLY:
            return "Complete the baseline assessment to unlock personalized coaching features."
        else:
            return "Assessment in progress. Complete it to access all features."
    
    def handle_partial_assessment_skip(self, user_id: str) -> Dict:
        """
        Handle case where user starts assessment then skips instead of resuming.
        
        Args:
            user_id: User ID
            
        Returns:
            Skip result
        """
        user = self.storage.get_user(user_id)
        if not user:
            return {
                'success': False,
                'reason': 'User not found'
            }
        
        # Discard partial data
        existing_assessment = self.storage.get_latest_assessment(user_id)
        if existing_assessment and not existing_assessment.completed_at:
            logger.info(f"Discarding partial assessment data for user {user_id}")
            # Would need to implement assessment deletion/cleanup
        
        # Set status to unassessed
        self.storage.update_user_assessment_status(user_id, AssessmentStatus.UNASSESSED)
        
        return {
            'success': True,
            'status': 'unassessed',
            'message': 'Partial assessment discarded. Complete the full assessment when ready.'
        }
    
    def get_user_feature_summary(self, user_id: str) -> Dict:
        """
        Get complete feature access summary for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Feature access summary
        """
        user = self.storage.get_user(user_id)
        if not user:
            return {
                'error': 'User not found'
            }
        
        access_level = self.get_access_level(user_id)
        features = self.get_accessible_features(user_id)
        
        return {
            'user_id': user_id,
            'display_name': user.display_name,
            'assessment_status': user.assessment_status.value,
            'access_level': access_level.value,
            'skip_prompt_count': self._get_skip_prompt_count(user_id),
            'show_assessment_prompt': self.should_show_assessment_prompt(user_id),
            'assessment_prompt_message': self.get_assessment_prompt_message(user_id) if self.should_show_assessment_prompt(user_id) else None,
            'accessible_features': features['accessible_features'],
            'inaccessible_features': features.get('inaccessible_features', []),
            'locked_message': features.get('locked_message')
        }