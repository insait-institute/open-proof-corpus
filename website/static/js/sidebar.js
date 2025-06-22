// --- Global state variables ---
let globalSidebarInfo = null;
let globalCurrentFile = null;
let globallyProcessedData = null;
let isSidebarCollapsed = false; // New state for collapsibility

const SIDEBAR_COLLAPSED_WIDTH = '60px'; // Width when collapsed
const SIDEBAR_EXPANDED_WIDTH = '320px'; // Original width

/**
 * Toggles the collapsed state of the sidebar.
 */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggleButton = document.getElementById('sidebar-toggle-button');
    const mainContent = document.querySelector('.main-content'); // Assume you have a main content wrapper

    isSidebarCollapsed = !isSidebarCollapsed;
    localStorage.setItem('sidebarCollapsed', isSidebarCollapsed); // Persist state

    if (isSidebarCollapsed) {
        sidebar.classList.add('collapsed');
        sidebar.style.width = SIDEBAR_COLLAPSED_WIDTH;
        if (toggleButton) toggleButton.innerHTML = '&#9776;'; // Hamburger icon
        if (mainContent) mainContent.style.marginLeft = SIDEBAR_COLLAPSED_WIDTH;
    } else {
        sidebar.classList.remove('collapsed');
        sidebar.style.width = SIDEBAR_EXPANDED_WIDTH;
        if (toggleButton) toggleButton.innerHTML = '&times;'; // Close icon
        if (mainContent) mainContent.style.marginLeft = SIDEBAR_EXPANDED_WIDTH;
    }
}


/**
 * Checks if a single question is fully completed.
 * A question is complete if all its status codes are 2.
 * @param {Array<number>} statusCodes - Array of status codes for a question.
 * @returns {boolean} - True if the question is completed, false otherwise.
 */
function isQuestionCompleted(statusCodes) {
    if (!statusCodes || statusCodes.length === 0) return false;
    return statusCodes.every(code => code === 2);
}

/**
 * Parses the raw sidebar_info into a structured object grouped by competitions,
 * including progress calculation.
 */
function processSidebarData(sidebar_info) {
    const { file_names, finished } = sidebar_info;
    const competitionsData = {};

    if (!file_names || file_names.length === 0) {
        return competitionsData;
    }

    file_names.forEach((fullName, i) => {
        const parts = fullName.split(':');
        let competitionName, questionName;

        if (parts.length > 1) {
            competitionName = parts[0].trim();
            questionName = parts.slice(1).join(':').trim();
        } else {
            competitionName = "General";
            questionName = fullName.trim();
        }

        if (!competitionsData[competitionName]) {
            competitionsData[competitionName] = {
                questions: [],
                totalQuestions: 0,
                completedQuestions: 0
            };
        }

        const questionStatusCodes = finished[i] || [];
        competitionsData[competitionName].questions.push({
            questionName: questionName,
            fullName: fullName,
            statusCodes: questionStatusCodes
        });

        competitionsData[competitionName].totalQuestions++;
        if (isQuestionCompleted(questionStatusCodes)) {
            competitionsData[competitionName].completedQuestions++;
        }
    });
    return competitionsData;
}

/**
 * Renders the sidebar content.
 */
function displaySidebar(activeCompetition = null) {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) {
        console.error("Sidebar element not found!");
        return;
    }
    sidebar.innerHTML = ''; // Clear previous content
    sidebar.dataset.activeCompetition = activeCompetition || '';


    // --- Create and Add Toggle Button (always first) ---
    const toggleButton = document.createElement('button');
    toggleButton.id = 'sidebar-toggle-button';
    toggleButton.className = 'sidebar-toggle-button';
    toggleButton.innerHTML = isSidebarCollapsed ? '&#9776;' : '&times;';
    toggleButton.title = isSidebarCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar';
    toggleButton.onclick = toggleSidebar;
    sidebar.appendChild(toggleButton);

    // This container is for the text part of the header, to allow hiding it
    const headerTextContainer = document.createElement('div');
    headerTextContainer.className = 'sidebar-header-text-container';

    // --- Create itemsList (will be populated later, but added to DOM after headers) ---
    const itemsList = document.createElement('div');
    itemsList.className = 'sidebar-items-list';

    // --- Handle View-Specific Static Elements (Return Button, Header) ---
    if (activeCompetition && globallyProcessedData && globallyProcessedData[activeCompetition]) {
        // --- Questions View ---
        const returnButton = document.createElement('button');
        returnButton.className = 'sidebar-return-button';
        returnButton.innerHTML = `<span class="arrow">&larr;</span> <span class="return-button-text">All Competitions</span>`;
        returnButton.onclick = () => displaySidebar(null);
        sidebar.appendChild(returnButton); // Add return button after toggle

        const header = document.createElement('div');
        header.className = 'sidebar-header';
        const competitionNameSpan = document.createElement('span');
        competitionNameSpan.textContent = activeCompetition;
        headerTextContainer.innerHTML = ''; // Clear for safety
        headerTextContainer.appendChild(competitionNameSpan);
        header.appendChild(headerTextContainer);
        sidebar.appendChild(header); // Add header after return button

    } else if (globallyProcessedData) { // For "Competitions" or general header if data exists
        // --- Competitions View ---
        const header = document.createElement('div');
        header.className = 'sidebar-header';
        const competitionsTitleSpan = document.createElement('span');
        competitionsTitleSpan.textContent = 'Competitions';
        headerTextContainer.innerHTML = ''; // Clear for safety
        headerTextContainer.appendChild(competitionsTitleSpan);
        header.appendChild(headerTextContainer);
        sidebar.appendChild(header); // Add header after toggle
    }
    // If globallyProcessedData is null, no specific header is added here;
    // the loading message will go into itemsList directly.

    // --- Append itemsList to the sidebar (now it's a child) ---
    sidebar.appendChild(itemsList);

    // --- Populate itemsList content ---
    if (!globallyProcessedData) {
        console.error("Sidebar data not processed yet.");
        const noDataMessage = document.createElement('div');
        noDataMessage.className = 'sidebar-item no-files-message';
        noDataMessage.textContent = 'Loading data...';
        itemsList.appendChild(noDataMessage); // Add message to itemsList
        // Apply collapsed state styling correctly even when loading
        if (isSidebarCollapsed && !sidebar.classList.contains('collapsed')) {
            sidebar.classList.add('collapsed');
            sidebar.style.width = SIDEBAR_COLLAPSED_WIDTH;
        }
        return; // Exit early as there's no data to display
    }


    if (activeCompetition && globallyProcessedData[activeCompetition]) {
        // --- Questions List in itemsList ---
        const competitionData = globallyProcessedData[activeCompetition];
        if (competitionData.questions.length === 0) {
            const noQuestionsMessage = document.createElement('div');
            noQuestionsMessage.className = 'sidebar-item no-files-message';
            noQuestionsMessage.textContent = 'No questions in this competition.';
            itemsList.appendChild(noQuestionsMessage);
        } else {
            competitionData.questions.forEach(q => {
                const listItem = document.createElement('a');
                listItem.href = `?file_name=${encodeURIComponent(q.fullName)}`;
                listItem.className = 'sidebar-item question-item';
                if (globalCurrentFile && q.fullName === globalCurrentFile) {
                    listItem.classList.add('current');
                }

                const itemContent = document.createElement('div');
                itemContent.className = 'sidebar-item-content';
                const nameSpan = document.createElement('span');
                nameSpan.className = 'file-name-sidebar';
                nameSpan.textContent = q.questionName;
                nameSpan.title = q.fullName;
                const statusSpan = document.createElement('span');
                statusSpan.className = 'file-status-sidebar';
                if (Array.isArray(q.statusCodes)) {
                    statusSpan.textContent = q.statusCodes.map(code => finishedSymbol(code)).join('');
                } else {
                    statusSpan.textContent = finishedSymbol(q.statusCodes);
                }
                itemContent.append(nameSpan, statusSpan);
                listItem.appendChild(itemContent);
                itemsList.appendChild(listItem);
            });
        }
    } else {
        // --- Competitions List in itemsList ---
        const competitionNames = Object.keys(globallyProcessedData);
        if (competitionNames.length === 0 && (!globalSidebarInfo || globalSidebarInfo.file_names.length === 0)) {
            const noFilesMessage = document.createElement('div');
            noFilesMessage.className = 'sidebar-item no-files-message';
            noFilesMessage.textContent = 'No files available.';
            itemsList.appendChild(noFilesMessage);
        } else if (competitionNames.length === 0) {
            const noCompsMessage = document.createElement('div');
            noCompsMessage.className = 'sidebar-item no-files-message';
            noCompsMessage.textContent = 'No competitions found.';
            itemsList.appendChild(noCompsMessage);
        } else {
            competitionNames.forEach(compName => {
                const competitionData = globallyProcessedData[compName];
                const listItem = document.createElement('div');
                listItem.className = 'sidebar-item competition-item';
                listItem.title = `View questions for ${compName}`;
                listItem.onclick = () => displaySidebar(compName);
                listItem.setAttribute('role', 'button');
                listItem.setAttribute('tabindex', '0');
                listItem.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') displaySidebar(compName); };

                const itemContent = document.createElement('div');
                itemContent.className = 'sidebar-item-content';
                const nameSpan = document.createElement('span');
                nameSpan.className = 'file-name-sidebar';
                nameSpan.textContent = compName;
                itemContent.appendChild(nameSpan);
                const arrowSpan = document.createElement('span');
                arrowSpan.className = 'competition-arrow';
                arrowSpan.innerHTML = '&#8250;';
                itemContent.appendChild(arrowSpan);
                listItem.appendChild(itemContent);

                const progressBarContainer = document.createElement('div');
                progressBarContainer.className = 'progress-bar-container';
                const progressBarFill = document.createElement('div');
                progressBarFill.className = 'progress-bar-fill';
                let progressPercent = 0;
                if (competitionData.totalQuestions > 0) {
                    progressPercent = (competitionData.completedQuestions / competitionData.totalQuestions) * 100;
                }
                progressBarFill.style.width = `${progressPercent}%`;
                progressBarContainer.appendChild(progressBarFill);
                listItem.appendChild(progressBarContainer);

                if (globalCurrentFile) {
                    const parts = globalCurrentFile.split(':');
                    if (parts.length > 0 && parts[0].trim() === compName) {
                        listItem.classList.add('current-competition-group');
                    }
                }
                itemsList.appendChild(listItem);
            });
        }
    }

    // Ensure correct collapsed state class and style are applied
    if (isSidebarCollapsed) {
        if (!sidebar.classList.contains('collapsed')) sidebar.classList.add('collapsed');
        sidebar.style.width = SIDEBAR_COLLAPSED_WIDTH;
    } else {
        if (sidebar.classList.contains('collapsed')) sidebar.classList.remove('collapsed');
        sidebar.style.width = SIDEBAR_EXPANDED_WIDTH;
    }


    requestAnimationFrame(() => {
        if (isSidebarCollapsed) return;

        if (globalCurrentFile) {
            const currentItem = sidebar.querySelector(`.sidebar-item.current`);
            if (currentItem && itemsList.contains(currentItem)) {
                currentItem.scrollIntoView({ behavior: 'auto', block: 'nearest', inline: 'nearest' });
            } else if (activeCompetition) {
                itemsList.scrollTop = 0;
            }
        } else if (!activeCompetition && Object.keys(globallyProcessedData).length > 0) {
            const currentCompGroup = sidebar.querySelector('.current-competition-group');
            if (currentCompGroup && itemsList.contains(currentCompGroup)) {
                currentCompGroup.scrollIntoView({ behavior: 'auto', block: 'nearest', inline: 'nearest' });
            } else {
                itemsList.scrollTop = 0;
            }
        }
    });
}

/**
 * Main entry point.
 */
function addFileNamesToSidebar(sidebar_info, current = null) {
    globalSidebarInfo = sidebar_info;
    globalCurrentFile = current;
    globallyProcessedData = processSidebarData(sidebar_info);

    const storedCollapsedState = localStorage.getItem('sidebarCollapsed');
    isSidebarCollapsed = storedCollapsedState === 'true';

    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.main-content');

    // Set initial width based on stored collapsed state BEFORE first displaySidebar call
    if (sidebar) { // Ensure sidebar element exists
        if (isSidebarCollapsed) {
            sidebar.classList.add('collapsed'); // Add class immediately
            sidebar.style.width = SIDEBAR_COLLAPSED_WIDTH;
            if (mainContent) mainContent.style.marginLeft = SIDEBAR_COLLAPSED_WIDTH;
        } else {
            sidebar.classList.remove('collapsed'); // Remove class if not collapsed
            sidebar.style.width = SIDEBAR_EXPANDED_WIDTH;
            if (mainContent) mainContent.style.marginLeft = SIDEBAR_EXPANDED_WIDTH;
        }
    }


    let initialCompetitionToDisplay = null;
    let activeFileIsActuallyInACompetition = false;

    if (current) {
        const parts = current.split(':');
        if (parts.length > 0) {
            const currentCompName = parts[0].trim();
            if (globallyProcessedData && globallyProcessedData[currentCompName]) {
                initialCompetitionToDisplay = currentCompName;
                activeFileIsActuallyInACompetition = true;
            } else {
                 console.warn(`Competition "${currentCompName}" from current file ("${current}") not found. Displaying competition list.`);
            }
        }
    }
    
    displaySidebar(initialCompetitionToDisplay); // This will now correctly build the UI

    const currentFileDisplay = document.getElementById('current-file-display');
    if (currentFileDisplay) {
        currentFileDisplay.textContent = current || "None";
    }

    if (activeFileIsActuallyInACompetition &&
        globallyProcessedData[initialCompetitionToDisplay] &&
        globallyProcessedData[initialCompetitionToDisplay].questions.length > 0) {
        return current || globallyProcessedData[initialCompetitionToDisplay].questions[0].fullName;

    } else if (sidebar_info && sidebar_info.file_names && sidebar_info.file_names.length > 0) {
        return current || sidebar_info.file_names[0];
    }
    return null;
}

/**
 * Maps a status code to an emoji symbol.
 */
function finishedSymbol(finished) {
    if (finished == 0) return '❌';
    if (finished == 1) return '⏳';
    return '✅';
}

// Initial setup on DOMContentLoaded if not handled by other script loading orders
document.addEventListener('DOMContentLoaded', () => {
   const sidebar = document.getElementById('sidebar');
   const mainContent = document.querySelector('.main-content');
   const storedCollapsedState = localStorage.getItem('sidebarCollapsed');
   isSidebarCollapsed = storedCollapsedState === 'true'; // Set global JS variable

   if (sidebar) { // Check if sidebar exists
       if (isSidebarCollapsed) {
           sidebar.classList.add('collapsed'); // Add class before any JS that might rely on it
           sidebar.style.width = SIDEBAR_COLLAPSED_WIDTH;
           if (mainContent) {
                mainContent.style.marginLeft = SIDEBAR_COLLAPSED_WIDTH;
           }
       } else {
           sidebar.classList.remove('collapsed');
           sidebar.style.width = SIDEBAR_EXPANDED_WIDTH;
           if (mainContent) {
                mainContent.style.marginLeft = SIDEBAR_EXPANDED_WIDTH;
           }
       }
   }
   // Your application would then typically call addFileNamesToSidebar with data
   // e.g., if using the example from previous response: loadSidebarData();
});