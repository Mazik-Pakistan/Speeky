"""
Simple Web UI for Baseline Assessment.

Flask web application providing web interface for Baseline Assessment features
while using the existing CLI backend.
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# Speeky imports
from speeky import (
    SpeekyPipeline,
    InMemoryStorage,
    ConfidenceScoreEngine,
    InitialCommunicationAssessment,
    ResultsSummaryView,
    FeatureAccessGating,
    PeriodicReAssessment,
    LearningLevel,
    AssessmentStatus
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'speeky-dev-secret-key'  # Change for production

# Initialize components globally
storage = InMemoryStorage()
confidence_engine = ConfidenceScoreEngine()
pipeline = SpeekyPipeline(confidence_engine=confidence_engine)
assessment_system = InitialCommunicationAssessment(pipeline, storage, confidence_engine)
results_view = ResultsSummaryView(storage, confidence_engine)
feature_gating = FeatureAccessGating(storage)
reassessment_system = PeriodicReAssessment(storage, assessment_system)

# Demo user (in production, this would come from external auth)
DEMO_USER_ID = None


def get_or_create_demo_user():
    """Get or create demo user for testing."""
    global DEMO_USER_ID
    
    if DEMO_USER_ID:
        user = storage.get_user(DEMO_USER_ID)
        if user:
            return user
    
    # Check if demo user already exists in storage
    existing_user = storage.get_user_by_external_id("demo_user_123")
    if existing_user:
        DEMO_USER_ID = existing_user.user_id
        return existing_user
    
    # Create demo user
    user = storage.create_user(
        external_id="demo_user_123",
        display_name="Demo User",
        is_enterprise=False
    )
    DEMO_USER_ID = user.user_id
    return user


@app.route('/')
def index():
    """Main dashboard page."""
    user = get_or_create_demo_user()
    
    # Get user's assessment status
    assessment_status = user.assessment_status.value
    latest_assessment = storage.get_latest_assessment(user.user_id)
    
    # Check if there's an active assessment in session or storage
    has_active_assessment = 'assessment_id' in session or storage.get_current_assessment(user.user_id) is not None
    
    # Get feature access summary
    feature_summary = feature_gating.get_user_feature_summary(user.user_id)
    
    # Get confidence score breakdown
    confidence_breakdown = confidence_engine.get_confidence_breakdown()
    
    # Check for re-assessment eligibility
    reassessment_summary = reassessment_system.get_re_assessment_summary(user.user_id)
    
    return render_template('index.html',
                         user=user,
                         assessment_status=assessment_status,
                         has_active_assessment=has_active_assessment,
                         latest_assessment=latest_assessment,
                         feature_summary=feature_summary,
                         confidence_breakdown=confidence_breakdown,
                         reassessment_summary=reassessment_summary)


@app.route('/assessment')
def assessment_page():
    """Assessment page for completing questions."""
    user = get_or_create_demo_user()
    
    # Check if there's an assessment in session
    if 'assessment_id' not in session:
        # Check if there's an assessment in storage
        assessment_data = storage.get_current_assessment(user.user_id)
        if assessment_data:
            # Restore session from storage
            session['assessment_id'] = assessment_data['assessment_id']
            session['current_question_index'] = assessment_data.get('current_question_index', 0)
            session['total_questions'] = len(assessment_data.get('questions', []))
        else:
            return redirect(url_for('index'))
    
    return render_template('assessment.html',
                         user=user,
                         assessment_id=session['assessment_id'],
                         total_questions=session.get('total_questions', 5),
                         current_question_index=session.get('current_question_index', 0))


@app.route('/assessment/start')
def start_assessment():
    """Start a new baseline assessment."""
    user = get_or_create_demo_user()
    
    try:
        result = assessment_system.start_assessment(user.user_id)
        session['assessment_id'] = result['assessment_id']
        session['current_question_index'] = 0
        session['total_questions'] = result['total_questions']
        
        return redirect(url_for('assessment_page'))
    except Exception as e:
        logger.error(f"Error starting assessment: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/assessment/question')
def get_current_question():
    """Get current assessment question."""
    if 'assessment_id' not in session:
        return jsonify({'success': False, 'error': 'No active assessment'})
    
    assessment_id = session['assessment_id']
    current_index = session.get('current_question_index', 0)
    user = get_or_create_demo_user()
    
    # Get current question from storage
    try:
        assessment_data = storage.get_current_assessment(user.user_id)
        
        if assessment_data and assessment_data.get('assessment_id') == assessment_id:
            questions = assessment_data['questions']
            if current_index < len(questions):
                current_question = questions[current_index].text
            else:
                current_question = "Assessment complete or index out of range"
            
            # Update assessment_system's current_assessment
            assessment_system.current_assessment = assessment_data
        else:
            current_question = "Assessment session expired. Please start a new assessment."
        
        return jsonify({
            'success': True,
            'assessment_id': assessment_id,
            'current_question_index': current_index,
            'total_questions': session.get('total_questions', 5),
            'current_question': current_question
        })
    except Exception as e:
        logger.error(f"Error getting question: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'current_question': 'Error loading question'
        })


@app.route('/assessment/submit', methods=['POST'])
def submit_response():
    """Submit response to current assessment question."""
    if 'assessment_id' not in session:
        return jsonify({'success': False, 'error': 'No active assessment'})
    
    data = request.json
    assessment_id = session['assessment_id']
    response_type = data.get('response_type', 'text')
    text_data = data.get('text_data')
    clipboard_detected = data.get('clipboard_detected', False)
    
    try:
        result = assessment_system.submit_response(
            assessment_id=assessment_id,
            response_type=response_type,
            text_data=text_data,
            clipboard_detected=clipboard_detected
        )
        
        if result['status'] == 'completed':
            # Clear session
            session.pop('assessment_id', None)
            session.pop('current_question_index', None)
            session.pop('total_questions', None)
            
            return jsonify({
                'success': True,
                'status': 'completed',
                'result': result
            })
        else:
            session['current_question_index'] = result['question_index']
            return jsonify({
                'success': True,
                'status': 'in_progress',
                'next_question': result['next_question'],
                'question_index': result['question_index'],
                'previous_result': result.get('previous_result')
            })
            
    except Exception as e:
        logger.error(f"Error submitting response: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/assessment/reset', methods=['POST'])
def reset_assessment():
    """Reset stuck assessment."""
    user = get_or_create_demo_user()
    storage.clear_current_assessment(user.user_id)
    storage.update_user_assessment_status(user.user_id, AssessmentStatus.UNASSESSED)
    session.pop('assessment_id', None)
    session.pop('current_question_index', None)
    session.pop('total_questions', None)
    return redirect(url_for('index'))


@app.route('/assessment/skip', methods=['POST'])
def skip_assessment():
    """Skip the baseline assessment."""
    user = get_or_create_demo_user()
    
    try:
        # Attempt to skip
        skip_result = feature_gating.attempt_skip_assessment(user.user_id)
        
        if skip_result.get('success') and skip_result.get('action_required') == 'confirm_skip':
            # User confirmed skip
            confirm_result = feature_gating.confirm_skip_assessment(user.user_id)
            return jsonify(confirm_result)
        else:
            return jsonify(skip_result)
            
    except Exception as e:
        logger.error(f"Error skipping assessment: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/results/<assessment_id>')
def view_results(assessment_id):
    """View assessment results."""
    try:
        summary = results_view.generate_assessment_summary(assessment_id)
        progress_comparison = results_view.generate_progress_comparison(summary['user_id'])
        
        return render_template('results.html',
                             summary=summary,
                             progress_comparison=progress_comparison)
    except Exception as e:
        logger.error(f"Error generating results: {e}")
        return f"Error generating results: {str(e)}"


@app.route('/api/confidence')
def get_confidence_score():
    """Get current confidence score."""
    breakdown = confidence_engine.get_confidence_breakdown()
    return jsonify(breakdown)


@app.route('/api/features')
def get_features():
    """Get accessible features."""
    user = get_or_create_demo_user()
    features = feature_gating.get_accessible_features(user.user_id)
    return jsonify(features)


@app.route('/api/reassessment/start', methods=['POST'])
def start_reassessment():
    """Start a re-assessment."""
    user = get_or_create_demo_user()
    
    try:
        result = reassessment_system.start_re_assessment(user.user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error starting re-assessment: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/reassessment/eligibility')
def get_reassessment_eligibility():
    """Get re-assessment eligibility."""
    user = get_or_create_demo_user()
    eligibility = reassessment_system.check_eligibility(user.user_id)
    
    return jsonify({
        'is_eligible': eligibility.is_eligible,
        'days_until_eligible': eligibility.days_until_eligible,
        'reason': eligibility.reason,
        'scheduled_date': eligibility.scheduled_date.isoformat() if eligibility.scheduled_date else None
    })


def create_templates():
    """Create HTML templates for the web UI."""
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    
    # Create base template
    base_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Speeky - Baseline Assessment</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 { color: #2c3e50; }
        h2 { color: #34495e; }
        .btn {
            background-color: #3498db;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        .btn:hover { background-color: #2980b9; }
        .btn-secondary {
            background-color: #95a5a6;
        }
        .btn-secondary:hover { background-color: #7f8c8d; }
        .score-card {
            background-color: #ecf0f1;
            padding: 20px;
            border-radius: 8px;
            margin: 10px 0;
        }
        .status-badge {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }
        .status-completed { background-color: #27ae60; color: white; }
        .status-unassessed { background-color: #e74c3c; color: white; }
        .status-in_progress { background-color: #f39c12; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎤 Speeky Baseline Assessment</h1>
            <p>Welcome, {{ user.display_name if user else 'Guest' }}</p>
        </header>
        
        {% block content %}{% endblock %}
    </div>
    
    <script>
        // Common JavaScript functions
        function apiCall(url, data = null) {
            const options = {
                method: data ? 'POST' : 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            };
            if (data) {
                options.body = JSON.stringify(data);
            }
            return fetch(url, options).then(r => r.json());
        }
    </script>
</body>
</html>'''
    
    with open(os.path.join(templates_dir, 'base.html'), 'w', encoding='utf-8') as f:
        f.write(base_template)
    
    # Create index template
    index_template = '''{% extends "base.html" %}
{% block content %}
<div class="dashboard">
    <h2>Your Assessment Status</h2>
    
    <div class="score-card">
        <p><strong>Status:</strong> 
            <span class="status-badge status-{{ assessment_status }}">{{ assessment_status|title }}</span>
        </p>
        
        {% if has_active_assessment %}
        <p><strong>Active Assessment:</strong> Assessment in progress</p>
        {% endif %}
        
        {% if latest_assessment and latest_assessment.completed_at %}
        <p><strong>Last Assessment:</strong> {{ latest_assessment.completed_at.strftime('%Y-%m-%d %H:%M') }}</p>
        <p><strong>Confidence Score:</strong> {{ latest_assessment.confidence_score|round(1) }}/100</p>
        <p><strong>Learning Level:</strong> {{ latest_assessment.learning_level.value|title }}</p>
        {% endif %}
    </div>
    
    <div class="score-card">
        <h3>Current Confidence Score</h3>
        <p><strong>Score:</strong> {{ confidence_breakdown.current_score|round(1) }}/100</p>
        <p><em>{{ confidence_breakdown.explanation }}</em></p>
        
        <h4>Score Breakdown:</h4>
        <ul>
            <li><strong>Fluency:</strong> {{ confidence_breakdown.components.fluency.weight }}% - {{ confidence_breakdown.components.fluency.recent_average|round(1) }}/100</li>
            <li><strong>Vocabulary:</strong> {{ confidence_breakdown.components.vocabulary.weight }}% - {{ confidence_breakdown.components.vocabulary.recent_average|round(1) }}/100</li>
            {% if confidence_breakdown.components.pronunciation.recent_average %}
            <li><strong>Pronunciation:</strong> {{ confidence_breakdown.components.pronunciation.weight }}% - {{ confidence_breakdown.components.pronunciation.recent_average|round(1) }}/100</li>
            {% endif %}
        </ul>
    </div>
    
    {% if assessment_status == 'unassessed' and not has_active_assessment %}
    <div class="score-card">
        <h3>Start Your Baseline Assessment</h3>
        <p>Complete a 5-minute AI-led evaluation to establish your communication baseline.</p>
        <button class="btn" onclick="startAssessment()">Start Assessment</button>
        <button class="btn btn-secondary" onclick="skipAssessment()">Skip for Now</button>
    </div>
    {% endif %}
    
    {% if has_active_assessment %}
    <div class="score-card">
        <h3>Assessment In Progress</h3>
        <p>You have an assessment in progress. Continue where you left off.</p>
        <button class="btn" onclick="continueAssessment()">Continue Assessment</button>
        <button class="btn btn-secondary" onclick="resetAssessment()">Reset Assessment</button>
    </div>
    {% endif %}
    
    {% if reassessment_summary.eligibility.is_eligible %}
    <div class="score-card">
        <h3>📅 Time for Re-Assessment</h3>
        <p>Your 30-day cycle is complete. Take a new assessment to track your progress!</p>
        <button class="btn" onclick="startReAssessment()">Start Re-Assessment</button>
    </div>
    {% endif %}
    
    <div class="score-card">
        <h3>Feature Access</h3>
        <p><strong>Access Level:</strong> {{ feature_summary.access_level|title }}</p>
        
        <h4>Accessible Features:</h4>
        <ul>
            {% for feature in feature_summary.accessible_features %}
            <li>{{ feature|replace('_', ' ')|title }}</li>
            {% endfor %}
        </ul>
        
        {% if feature_summary.inaccessible_features %}
        <h4>Locked Features (Complete Assessment to Unlock):</h4>
        <ul>
            {% for feature in feature_summary.inaccessible_features %}
            <li>{{ feature|replace('_', ' ')|title }}</li>
            {% endfor %}
        </ul>
        {% endif %}
    </div>
</div>

<script>
function startAssessment() {
    apiCall('/assessment/start')
        .then(data => {
            if (data.success) {
                window.location.href = '/assessment/progress';
            } else {
                alert('Error starting assessment: ' + data.error);
            }
        });
}

function skipAssessment() {
    if (confirm('Are you sure you want to skip the assessment? You will not be able to access coaching features without it.')) {
        apiCall('/assessment/skip', {})
            .then(data => {
                if (data.success) {
                    alert('Assessment skipped. Complete it later to unlock all features.');
                    location.reload();
                } else {
                    alert('Error: ' + (data.reason || data.error));
                }
            });
    }
}

function startReAssessment() {
    apiCall('/api/reassessment/start', {})
        .then(data => {
            if (data.success) {
                window.location.href = '/assessment/progress';
            } else {
                alert('Error starting re-assessment: ' + data.reason);
            }
        });
}

function continueAssessment() {
    window.location.href = '/assessment';
}

function resetAssessment() {
    if (confirm('Are you sure you want to reset the assessment? This will discard your progress.')) {
        fetch('/assessment/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(() => {
            window.location.href = '/';
        })
        .catch(error => {
            alert('Error resetting assessment');
            console.error(error);
        });
    }
}
</script>
{% endblock %}'''
    
    with open(os.path.join(templates_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_template)
    
    # Create results template
    results_template = '''{% extends "base.html" %}
{% block content %}
<div class="results">
    <h2>🎯 Assessment Results</h2>
    
    <div class="score-card">
        <h3>{{ summary.positive_framing.title }}</h3>
        <p><em>{{ summary.positive_framing.subtitle }}</em></p>
        <p>{{ summary.positive_framing.message }}</p>
    </div>
    
    <div class="score-card">
        <h3>Overall Confidence Score</h3>
        <h1 style="color: #3498db;">{{ summary.confidence_score.display }}</h1>
        <p><em>{{ summary.confidence_score.message }}</em></p>
    </div>
    
    <div class="score-card">
        <h3>Skill Breakdown</h3>
        <ul>
            <li>
                <strong>{{ summary.skill_breakdown.fluency.label }}:</strong> 
                {{ summary.skill_breakdown.fluency.display }} - {{ summary.skill_breakdown.fluency.description }}
            </li>
            <li>
                <strong>{{ summary.skill_breakdown.vocabulary.label }}:</strong> 
                {{ summary.skill_breakdown.vocabulary.display }} - {{ summary.skill_breakdown.vocabulary.description }}
            </li>
            {% if summary.skill_breakdown.pronunciation %}
            <li>
                <strong>{{ summary.skill_breakdown.pronunciation.label }}:</strong> 
                {{ summary.skill_breakdown.pronunciation.display }} - {{ summary.skill_breakdown.pronunciation.description }}
            </li>
            {% endif %}
        </ul>
    </div>
    
    <div class="score-card">
        <h3>Your Learning Level</h3>
        <p><strong>{{ summary.learning_level.label }}</strong></p>
        <p>Based on your confidence score, you're at the {{ summary.learning_level.label|lower }} level.</p>
    </div>
    
    <div class="score-card">
        <h3>Next Steps</h3>
        <ul>
            {% for step in summary.next_steps %}
            <li>{{ step }}</li>
            {% endfor %}
        </ul>
    </div>
    
    {% if progress_comparison %}
    <div class="score-card">
        <h3>📈 Your Progress</h3>
        <p><strong>Days Between Assessments:</strong> {{ progress_comparison.days_between }}</p>
        <p><strong>Total Assessments:</strong> {{ progress_comparison.assessment_count }}</p>
        
        <h4>Improvements:</h4>
        <ul>
            <li>
                <strong>Confidence:</strong> 
                <span style="color: {% if progress_comparison.improvements.confidence.positive %}green{% else %}red{% endif %}">
                    {{ progress_comparison.improvements.confidence.display }}
                </span>
            </li>
            <li>
                <strong>Fluency:</strong> 
                <span style="color: {% if progress_comparison.improvements.fluency.positive %}green{% else %}red{% endif %}">
                    {{ progress_comparison.improvements.fluency.display }}
                </span>
            </li>
            <li>
                <strong>Vocabulary:</strong> 
                <span style="color: {% if progress_comparison.improvements.vocabulary.positive %}green{% else %}red{% endif %}">
                    {{ progress_comparison.improvements.vocabulary.display }}
                </span>
            </li>
        </ul>
        
        {% if progress_comparison.level_progression.improved %}
        <p style="color: green;"><strong>🎉 Level Up! You progressed from {{ progress_comparison.level_progression.from }} to {{ progress_comparison.level_progression.to }}!</strong></p>
        {% endif %}
    </div>
    {% endif %}
    
    <button class="btn" onclick="window.location.href='/'">Back to Dashboard</button>
</div>
{% endblock %}'''
    
    with open(os.path.join(templates_dir, 'results.html'), 'w', encoding='utf-8') as f:
        f.write(results_template)
    
    # Create assessment template
    assessment_template = '''{% extends "base.html" %}
{% block content %}
<div class="assessment">
    <h2>Baseline Assessment</h2>
    
    <div class="score-card">
        <h3>Question {{ current_question_index + 1 }} of {{ total_questions }}</h3>
        <div id="question-container">
            <p id="question-text">Loading question...</p>
        </div>
        
        <div class="response-section">
            <h4>Your Response:</h4>
            <textarea id="response-text" rows="4" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px;" placeholder="Type your answer here..."></textarea>
            
            <div style="margin-top: 15px;">
                <button class="btn" onclick="submitResponse()">Submit Answer</button>
                <button class="btn btn-secondary" onclick="cancelAssessment()">Cancel Assessment</button>
            </div>
        </div>
        
        <div id="result-container" style="display: none; margin-top: 20px;">
            <h4>Processing Result:</h4>
            <div id="result-content"></div>
        </div>
    </div>
</div>

<script>
let assessmentId = '{{ assessment_id }}';
let questionIndex = {{ current_question_index }};

function loadQuestion() {
    fetch('/assessment/question')
        .then(data => data.json())
        .then(data => {
            if (data.success) {
                document.getElementById('question-text').textContent = data.current_question || 'Question not available';
                questionIndex = data.current_question_index;
            } else {
                alert('Error loading question: ' + data.error);
            }
        });
}

function submitResponse() {
    const textData = document.getElementById('response-text').value;
    
    if (!textData.trim()) {
        alert('Please enter your response');
        return;
    }
    
    const data = {
        response_type: 'text',
        text_data: textData,
        clipboard_detected: false
    };
    
    fetch('/assessment/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'completed') {
            // Assessment complete
            window.location.href = '/results/' + assessmentId;
        } else if (result.status === 'in_progress') {
            // Next question
            document.getElementById('response-text').value = '';
            document.getElementById('question-text').textContent = result.next_question;
            questionIndex = result.question_index;
        } else {
            alert('Error: ' + (result.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error submitting response: ' + error);
    });
}

function cancelAssessment() {
    if (confirm('Are you sure you want to cancel the assessment?')) {
        fetch('/assessment/skip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = '/';
            } else {
                alert('Error: ' + (data.reason || data.error));
            }
        });
    }
}

// Load initial question
loadQuestion();
</script>
{% endblock %}'''
    
    with open(os.path.join(templates_dir, 'assessment.html'), 'w', encoding='utf-8') as f:
        f.write(assessment_template)
    
    logger.info(f"Templates created in {templates_dir}")


if __name__ == '__main__':
    # Create templates on startup
    create_templates()
    
    # Run Flask app
    app.run(debug=False, host='0.0.0.0', port=5000)