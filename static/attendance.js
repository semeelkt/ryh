/**
 * Attendance System JavaScript
 * Handles timetable checking, form submission, and dynamic updates
 */

/**
 * Check if current time falls within an active class session
 * Compares current time with teacher's timetable
 */
function checkActiveSession() {
    console.log('Checking active session...');

    fetch('/api/teacher/timetable')
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch timetable');
            return response.json();
        })
        .then(timetables => {
            const now = new Date();
            const currentTime = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
            const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
            const currentDay = dayNames[now.getDay()];

            console.log(`Current time: ${currentTime}, Day: ${currentDay}`);

            // Find active session
            const activeSession = timetables.find(t => {
                return t.day_of_week === currentDay &&
                       t.start_time <= currentTime &&
                       t.end_time >= currentTime;
            });

            if (activeSession) {
                showActiveSessionMessage(activeSession);
                showMarkAttendanceButton();
            } else {
                showNoSessionMessage();
                hideMarkAttendanceButton();
            }
        })
        .catch(error => {
            console.error('Error checking active session:', error);
        });
}

/**
 * Display active session details
 */
function showActiveSessionMessage(session) {
    const statusDiv = document.getElementById('session-status');
    if (statusDiv) {
        statusDiv.innerHTML = `
            <div class="bg-green-900/30 border border-green-700 rounded-lg p-4">
                <p class="text-green-300 font-semibold">✓ Active Session</p>
                <p class="text-green-200 text-sm mt-1"><strong>${session.subject_name}</strong></p>
                <p class="text-green-200 text-xs">${session.start_time} - ${session.end_time}</p>
            </div>
        `;
    }
}

/**
 * Display no session message
 */
function showNoSessionMessage() {
    const statusDiv = document.getElementById('session-status');
    if (statusDiv) {
        statusDiv.innerHTML = `
            <div class="bg-gray-700 rounded-lg p-4">
                <p class="text-gray-300">No Active Session</p>
                <p class="text-gray-400 text-sm mt-1">Check back during class hours</p>
            </div>
        `;
    }
}

/**
 * Show mark attendance button
 */
function showMarkAttendanceButton() {
    const btnDiv = document.getElementById('mark-attendance-btn');
    if (btnDiv) {
        btnDiv.classList.remove('hidden');
    }
}

/**
 * Hide mark attendance button
 */
function hideMarkAttendanceButton() {
    const btnDiv = document.getElementById('mark-attendance-btn');
    if (btnDiv) {
        btnDiv.classList.add('hidden');
    }
}

/**
 * Submit attendance form via XHR
 */
function submitAttendanceForm(formElement) {
    event.preventDefault();

    const formData = new FormData(formElement);
    const data = {
        classroom_id: parseInt(formData.get('classroom_id')),
        date: formData.get('attendance_date'),
        period_name: formData.get('period_name'),
        attendance_list: collectAttendanceData()
    };

    fetch('{{ url_for("mark_attendance") }}', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            showNotification('Attendance submitted successfully!', 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            showNotification('Error: ' + (result.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error submitting attendance', 'error');
    });
}

/**
 * Collect attendance data from form
 */
function collectAttendanceData() {
    const data = [];
    const toggles = document.querySelectorAll('[data-student-id]');

    toggles.forEach(toggle => {
        const studentId = parseInt(toggle.dataset.studentId);
        const status = toggle.checked ? 'Present' : 'Absent';
        data.push({ student_id: studentId, status: status });
    });

    return data;
}

/**
 * Show notification message
 */
function showNotification(message, type = 'info') {
    const bgColor = type === 'success' ? 'bg-green-600' : 'bg-red-600';
    const notif = document.createElement('div');
    notif.className = `fixed top-4 right-4 ${bgColor} text-white px-6 py-3 rounded-lg shadow-lg`;
    notif.textContent = message;
    document.body.appendChild(notif);

    setTimeout(() => {
        notif.remove();
    }, 3000);
}

/**
 * Toggle student present/absent status
 */
function toggleAttendance(studentId, checked) {
    const status = checked ? 'Present' : 'Absent';
    console.log(`Student ${studentId} marked as ${status}`);
}

/**
 * Initialize page on load
 */
document.addEventListener('DOMContentLoaded', function() {
    // Check active session if on teacher dashboard
    if (document.getElementById('session-status')) {
        checkActiveSession();
        // Re-check every minute
        setInterval(checkActiveSession, 60000);
    }
});

/**
 * Format time for display (HH:MM)
 */
function formatTime(time) {
    if (typeof time === 'string' && time.includes(':')) {
        return time.substring(0, 5);
    }
    return time;
}

/**
 * Convert 24-hour time to 12-hour format
 */
function formatTime12Hour(time) {
    if (!time) return time;
    const [hours, minutes] = time.split(':');
    const hour = parseInt(hours);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const hour12 = hour % 12 || 12;
    return `${hour12}:${minutes} ${ampm}`;
}
