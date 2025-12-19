// Piazza AI Assistant - Content Script
// Detects the current post ID from the URL and fetches AI answers

const API_BASE_URL = 'http://localhost:5000';

function extractNetworkIdFromUrl() {
  // Piazza URLs look like: https://piazza.com/class/merk8zm4in1ib/post/940
  const url = window.location.href;
  const networkMatch = url.match(/\/class\/([^\/]+)/);
  if (networkMatch) {
    return networkMatch[1];
  }
  return null;
}

function extractPostIdFromUrl() {
  // Piazza URLs look like: https://piazza.com/class/merk8zm4in1ib/post/940
  const url = window.location.href;

  // Extract from /post/940 format
  const postMatch = url.match(/\/post\/(\d+)/);
  if (postMatch) {
    return parseInt(postMatch[1], 10);
  }

  return null;
}

async function fetchAnswer(networkId, postId) {
  try {
    const response = await fetch(`${API_BASE_URL}/answer?network_id=${networkId}&post_id=${postId}`);

    if (!response.ok) {
      if (response.status === 404) {
        const data = await response.json();
        console.log('[Piazza AI] No answer found:', data.message || 'Answer not in database');
        return null;
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('[Piazza AI] Error fetching answer:', error);
    return null;
  }
}

function formatAnswerWithCitations(answerText) {
  // Regex to match lecture citations: [Lecture: Title, Timestamp: HH:MM:SS,MS]
  const citationRegex = /\[Lecture:\s*([^\]]+?),\s*Timestamp:\s*(\d{2}:\d{2}:\d{2}),\d+\]/g;

  // Replace citations with styled spans - remove labels and milliseconds
  const formattedText = answerText.replace(citationRegex, (_, title, timestamp) => {
    return `<span style="color: #ff8c00;">[<i>${title}</i>, ${timestamp}]</span>`;
  });

  // Convert newlines to <br>
  return formattedText.replace(/\n/g, '<br>');
}

function insertAnswerIntoDOM(answerData) {
  // Find the article element with id="qaContentViewId"
  const articleElement = document.getElementById('qaContentViewId');

  if (!articleElement) {
    console.log('[Piazza AI] Could not find qaContentViewId element');
    return;
  }

  console.log('[Piazza AI] Found qaContentViewId element:', articleElement);

  // Remove any existing AI answer to avoid duplicates
  const existingAnswer = document.getElementById('piazza-ai-answer');
  if (existingAnswer) {
    console.log('[Piazza AI] Removing existing answer');
    existingAnswer.remove();
  }

  const existingHr = document.getElementById('piazza-ai-hr');
  if (existingHr) {
    console.log('[Piazza AI] Removing existing HR');
    existingHr.remove();
  }

  // Create the HR element
  const hr = document.createElement('hr');
  hr.className = 'my-0 mx-2';
  hr.id = 'piazza-ai-hr';

  // Format the answer text with styled citations
  const formattedAnswer = formatAnswerWithCitations(answerData.answer);

  // Format the timestamp
  const createdAt = new Date(answerData.created_at);
  const timestamp = createdAt.toLocaleString();

  // Create the answer div
  const answerDiv = document.createElement('div');
  answerDiv.id = 'piazza-ai-answer';
  answerDiv.style.padding = '0 0 0 38px';
  answerDiv.style.margin = '0 0.5rem';
  answerDiv.style.borderLeft = '3px solid #007bff';
  answerDiv.style.maxHeight = '0';
  answerDiv.style.overflow = 'hidden';
  answerDiv.style.transition = 'max-height 0.5s ease-in-out';
  answerDiv.innerHTML = `
    <div style="padding: 15px 0">
      <strong style="font-size: 1.125em; color: #007bff;">Piazza Bot:</strong>
      <div style="font-size: 0.85em; color: #666; margin-top: 2px;">Generated on ${timestamp}</div>
      <div style="white-space: pre-wrap; line-height: 1.6; margin-top: 10px;">${formattedAnswer.trim()}</div>
    </div>
  `;

  // Insert HR after the article element
  articleElement.insertAdjacentElement('afterend', hr);

  // Insert answer div after the HR
  hr.insertAdjacentElement('afterend', answerDiv);

  console.log('[Piazza AI] Answer inserted into DOM');
  console.log('[Piazza AI] HR element:', hr);
  console.log('[Piazza AI] Answer div:', answerDiv);
  console.log('[Piazza AI] Answer div parent:', answerDiv.parentElement);

  // Trigger the slide-down animation
  setTimeout(() => {
    // Get the actual height of the content
    const actualHeight = answerDiv.scrollHeight;
    answerDiv.style.maxHeight = actualHeight + 'px';
  }, 50);
}

async function checkCurrentPost() {
  const networkId = extractNetworkIdFromUrl();
  const postId = extractPostIdFromUrl();

  if (postId && networkId) {
    console.log(`[Piazza AI] Current post - Network: ${networkId}, Post ID: ${postId}`);

    // Fetch answer from API
    const answerData = await fetchAnswer(networkId, postId);

    if (answerData) {
      console.log('[Piazza AI] Answer found!');
      console.log('Status:', answerData.status);
      console.log('Course:', answerData.course);
      console.log('Answer:', answerData.answer);
      console.log('---');

      // Don't show anything if the answer is NO RESPONSE
      if (answerData.answer === 'NO RESPONSE') {
        console.log('[Piazza AI] Answer is NO RESPONSE, not displaying');
        return;
      }

      // Wait 1 second for Piazza to finish rendering
      console.log('[Piazza AI] Waiting 1 second for page to stabilize...');
      setTimeout(() => {
        insertAnswerIntoDOM(answerData);
      }, 500);
    }
  } else {
    console.log('[Piazza AI] Not viewing a specific post');
  }
}

// Check immediately when script loads
checkCurrentPost();

// Listen for URL changes (Piazza is a single-page app)
let lastUrl = window.location.href;
const urlObserver = new MutationObserver(() => {
  const currentUrl = window.location.href;
  if (currentUrl !== lastUrl) {
    lastUrl = currentUrl;
    console.log('[Piazza AI] URL changed, checking post...');
    checkCurrentPost();
  }
});

// Observe the document for changes
urlObserver.observe(document.body, {
  childList: true,
  subtree: true
});

// Also listen to popstate events (back/forward buttons)
window.addEventListener('popstate', () => {
  console.log('[Piazza AI] Navigation detected (popstate)');
  checkCurrentPost();
});

// Also listen to hashchange events
window.addEventListener('hashchange', () => {
  console.log('[Piazza AI] Hash changed');
  checkCurrentPost();
});

console.log('[Piazza AI] Extension loaded and monitoring for post changes');
