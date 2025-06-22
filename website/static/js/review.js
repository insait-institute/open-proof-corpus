const problemsContainer = document.getElementById('problemsContainer');
const paginationControlsContainerTop = document.getElementById('paginationControlsContainerTop'); // New top container
const paginationControlsContainerBottom = document.getElementById('paginationControlsContainer'); // Existing bottom container (renamed for clarity)

// --- Pagination Variables ---
let currentPage = 1;
const problemsPerPage = 30;

// --- Existing Functions (mostly unchanged, ensure `index` is original index) ---
function createProblemFeedbackForm(formId, placeholderText, data, problemIndex) {
    const form = document.createElement("form");
    form.id = formId;
    form.className = "mt-3";
    form.style.display = "none"; 

    const formGroup = document.createElement("div");
    formGroup.className = "mb-3";

    const textarea = document.createElement("textarea");
    textarea.className = "form-control";
    textarea.id = `feedbackTextarea-${problemIndex}`; 
    textarea.rows = 5;
    textarea.value = data.problem; 

    formGroup.appendChild(textarea);
    form.appendChild(formGroup);

    // --- Add Delete Problem Checkbox ---
    const deleteFormGroup = document.createElement("div");
    deleteFormGroup.className = "form-check mb-3";

    const deleteCheckbox = document.createElement("input");
    deleteCheckbox.className = "form-check-input";
    deleteCheckbox.type = "checkbox";
    deleteCheckbox.id = `deleteProblemCheckbox-${problemIndex}`;
    deleteCheckbox.checked = data.delete === true; // Pre-check if data.delete is true

    const deleteLabel = document.createElement("label");
    deleteLabel.className = "form-check-label text-danger"; // Added text-danger for emphasis
    deleteLabel.htmlFor = `deleteProblemCheckbox-${problemIndex}`;
    deleteLabel.textContent = "Mark for Deletion";

    deleteFormGroup.appendChild(deleteCheckbox);
    deleteFormGroup.appendChild(deleteLabel);
    form.appendChild(deleteFormGroup);
    // --- End of Delete Problem Checkbox ---

    const save = createSaveButton(problemIndex); 
    save.saveBtn.onclick = () => saveProblemChanges(problemIndex); 
    // save.statusPill.classList.remove("d-none"); // Status pill is handled by updateStatus
    form.appendChild(save.actionGroup);
    return form;
}

function renderProblemStatementReview(data, originalIndex, container) { 
    const problemWrapper = document.createElement("div");
    problemWrapper.className = "problem-item mb-4 p-3 border rounded shadow-sm"; 
    // If problem is marked as deleted, you might want to add a class here to style it differently
    if (data.delete === true) {
        problemWrapper.classList.add('problem-deleted-visual'); // Example class
        // You might also want to disable editing or show a "Marked for deletion" message more prominently
    }


    const problemLabel = document.createElement("h5");
    problemLabel.innerHTML = `Problem ${originalIndex + 1}`; 
    problemLabel.style.fontWeight = "bold";
    problemLabel.style.marginTop = "20px";
    problemWrapper.appendChild(problemLabel);

    const problemBox = document.createElement("div");
    problemBox.className = "marked box problem-box p-2 bg-light rounded"; 
    problemBox.style.whiteSpace = "pre-wrap";
    problemBox.style.tabSize = "4";
    
    // If problem is marked as deleted, perhaps strike-through the text or add an indicator
    if (data.delete === true) {
        const s = document.createElement('s');
        s.textContent = data.problem;
        problemBox.appendChild(s);
        const deletedIndicator = document.createElement('p');
        deletedIndicator.className = 'text-danger fw-bold mt-1';
        deletedIndicator.textContent = '(Marked for deletion)';
        problemBox.appendChild(deletedIndicator);

    } else {
        const textNode = document.createTextNode(data.problem);
        problemBox.appendChild(textNode);
    }
    problemBox.id = `problem-item-${originalIndex}`; 
    

    if (data.images && data.images.length > 0) {
        const gallery = buildImageGallery(data.images);
        problemBox.appendChild(gallery);
    }
    problemWrapper.appendChild(problemBox);
    
    const feedbackToggleDiv = document.createElement("div");
    feedbackToggleDiv.className = "form-check mt-3";
    
    const feedbackCheckbox = document.createElement("input");
    feedbackCheckbox.className = "form-check-input";
    feedbackCheckbox.type = "checkbox";
    feedbackCheckbox.id = `feedbackToggle-${originalIndex}`; 
    
    const feedbackCheckboxLabel = document.createElement("label");
    feedbackCheckboxLabel.className = "form-check-label";
    feedbackCheckboxLabel.htmlFor = `feedbackToggle-${originalIndex}`; 
    feedbackCheckboxLabel.textContent = data.delete === true ? "Edit/Unmark Deletion" : "Edit this problem";
    
    feedbackToggleDiv.appendChild(feedbackCheckbox);
    feedbackToggleDiv.appendChild(feedbackCheckboxLabel);
    problemWrapper.appendChild(feedbackToggleDiv);

    const feedbackForm = createProblemFeedbackForm(
        `problem-feedback-${originalIndex}`, 
        "Edit the problem statement...",
        data, // Pass the whole data object which might contain the 'delete' flag
        originalIndex 
    );
    problemWrapper.appendChild(feedbackForm);

    feedbackCheckbox.onchange = function() {
        feedbackForm.style.display = this.checked ? "block" : "none";
    };

    container.appendChild(problemWrapper);
}

async function saveProblemChanges(problemIndex) { 
    const feedbackTextareaElement = document.getElementById(`feedbackTextarea-${problemIndex}`);
    const problemTextElement = document.getElementById(`problem-item-${problemIndex}`);
    const statusPill = document.getElementById(`status-form-${problemIndex}`);
    const deleteCheckboxElement = document.getElementById(`deleteProblemCheckbox-${problemIndex}`); // Get delete checkbox

    if (!feedbackTextareaElement || !problemTextElement || !deleteCheckboxElement) {
        console.error(`Elements not found for problem index ${problemIndex}`);
        return;
    }

    const updatedProblemText = feedbackTextareaElement.value;
    const toBeDeleted = deleteCheckboxElement.checked; // Get delete status

    // Update the display element
    problemTextElement.innerHTML = ""; 
    if (toBeDeleted) {
        const s = document.createElement('s');
        s.textContent = updatedProblemText;
        problemTextElement.appendChild(s);
         const deletedIndicator = document.createElement('p');
        deletedIndicator.className = 'text-danger fw-bold mt-1';
        deletedIndicator.textContent = '(Marked for deletion)';
        problemTextElement.appendChild(deletedIndicator);
    } else {
        const textNode = document.createTextNode(updatedProblemText);
        problemTextElement.appendChild(textNode);
    }
    
    if (typeof renderMathInElement === 'function') {
        renderMathInElement(problemTextElement, {
            delimiters: [
              {left: '$$', right: '$$', display: true},
              {left: '$', right: '$', display: false},
              {left: '\\(', right: '\\)', display: false},
              {left: '\\[', right: '\\]', display: true}
            ],
            output: "htmlAndMathml",
            throwOnError: false
        });
    } else {
        console.warn("renderMathInElement is not defined. KaTeX might not re-render for edits.");
    }

    // 1. Update client-side data
    if (problemsData && problemsData[problemIndex]) {
        problemsData[problemIndex].problem = updatedProblemText;
        problemsData[problemIndex].delete = toBeDeleted; // Store delete status
    } else {
        console.error(`problemsData not found or invalid for index ${problemIndex}`);
        return;
    }
    
    // Update the "Edit this problem" label if the delete status changed
    const feedbackCheckboxLabel = document.querySelector(`label[for="feedbackToggle-${problemIndex}"]`);
    if (feedbackCheckboxLabel) {
        feedbackCheckboxLabel.textContent = toBeDeleted ? "Edit/Unmark Deletion" : "Edit this problem";
    }
     const problemWrapper = problemTextElement.closest('.problem-item');
    if (problemWrapper) {
        if (toBeDeleted) {
            problemWrapper.classList.add('problem-deleted-visual');
        } else {
            problemWrapper.classList.remove('problem-deleted-visual');
        }
    }


    // 2. Send to Flask
    try {
        const response = await fetch(`/update-problem/${fileId}/${problemIndex}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                problem: updatedProblemText,
                delete: toBeDeleted // Send delete status to server
            }),
        });
        if (statusPill) {
            updateStatus(response, statusPill);
        }
    } catch (error) {
        console.error('Error saving problem changes:', error);
        if (statusPill) {
            statusPill.classList.remove('d-none', 'bg-success', 'bg-warning');
            statusPill.classList.add('bg-danger');
            statusPill.textContent = 'Network Error';
             setTimeout(() => {
                statusPill.classList.add('d-none');
                statusPill.textContent = '';
            }, 3000);
        }
    }
}

document.getElementById('downloadButton').addEventListener('click', function() {
    // Filter out problems marked for deletion before downloading, if desired
    // const problemsToDownload = problemsData.filter(p => !(p.delete === true));
    // const jsonStr = JSON.stringify(problemsToDownload, null, 4); 
    // Or download all, including the delete flag:
    const jsonStr = JSON.stringify(problemsData, null, 4); 

    const filename = `edited_${fileId}.json`; 
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
});

// --- Pagination Functions ---
function renderCurrentPageProblems() {
    if (!problemsContainer) {
        console.error("problemsContainer not found in the DOM.");
        return;
    }
    problemsContainer.innerHTML = ''; 

    if (!Array.isArray(problemsData)) {
        console.error("Problems data is not an array:", problemsData);
        problemsContainer.textContent = "Error: Could not load problems data correctly.";
        return;
    }
    if (problemsData.length === 0) {
        problemsContainer.textContent = "No problems to display.";
        return;
    }

    const startIndex = (currentPage - 1) * problemsPerPage;
    const endIndex = Math.min(startIndex + problemsPerPage, problemsData.length);
    
    // If you want to filter out deleted problems from view entirely:
    // const allNonDeletedProblems = problemsData.filter(p => !(p.delete === true));
    // const totalPages = Math.ceil(allNonDeletedProblems.length / problemsPerPage); // Recalculate total pages
    // const problemsToRender = allNonDeletedProblems.slice(startIndex, endIndex);
    // problemsToRender.forEach((problem, indexOnPage) => {
    //    const originalIndex = problemsData.indexOf(problem); // Find original index if needed for saving
    //    renderProblemStatementReview(problem, originalIndex, problemsContainer);
    // });
    // For now, we'll show all problems, and deleted ones will be styled differently.

    const problemsToRender = problemsData.slice(startIndex, endIndex);

    problemsToRender.forEach((problem, indexOnPage) => {
        const originalIndex = startIndex + indexOnPage; 
        renderProblemStatementReview(problem, originalIndex, problemsContainer);
    });

    if (typeof renderMathInElement === 'function') {
        renderMathInElement(problemsContainer, {
            delimiters: [
              {left: '$$', right: '$$', display: true},
              {left: '$', right: '$', display: false},
              {left: '\\(', right: '\\)', display: false},
              {left: '\\[', right: '\\]', display: true}
            ],
            output: "htmlAndMathml",
            throwOnError: false
        });
    } else {
        console.warn("renderMathInElement is not defined. KaTeX might not render for the page.");
    }
}

/**
 * Renders pagination controls into a given container element.
 * @param {HTMLElement} container - The HTML element to render controls into.
 */
function renderPaginationControls(container) {
    if (!container) {
        // console.warn("Pagination container not found for rendering controls.");
        return;
    }
    container.innerHTML = ''; 

    if (!Array.isArray(problemsData) || problemsData.length === 0) {
        return; 
    }
    // If filtering deleted problems from view, base totalPages on the filtered list
    // const itemCount = problemsData.filter(p => !(p.delete === true)).length;
    // const totalPages = Math.ceil(itemCount / problemsPerPage);
    const totalPages = Math.ceil(problemsData.length / problemsPerPage);


    if (totalPages <= 1) {
        return; 
    }

    const nav = document.createElement('nav');
    nav.setAttribute('aria-label', 'Problems pagination');
    const ul = document.createElement('ul');
    ul.className = 'pagination';

    const prevLi = document.createElement('li');
    prevLi.className = `page-item ${currentPage === 1 ? 'disabled' : ''}`;
    const prevA = document.createElement('a');
    prevA.className = 'page-link';
    prevA.href = '#';
    prevA.textContent = 'Previous';
    prevA.addEventListener('click', (e) => {
        e.preventDefault();
        if (currentPage > 1) {
            goToPage(currentPage - 1);
        }
    });
    prevLi.appendChild(prevA);
    ul.appendChild(prevLi);
    
    const MAX_VISIBLE_PAGES = 7; 
    let startPage, endPage;

    if (totalPages <= MAX_VISIBLE_PAGES) {
        startPage = 1;
        endPage = totalPages;
    } else {
        const maxPagesBeforeCurrent = Math.floor((MAX_VISIBLE_PAGES - 3) / 2); 
        const maxPagesAfterCurrent = Math.ceil((MAX_VISIBLE_PAGES - 3) / 2);

        if (currentPage <= maxPagesBeforeCurrent + 1) { 
            startPage = 1;
            endPage = MAX_VISIBLE_PAGES - 2; 
        } else if (currentPage + maxPagesAfterCurrent >= totalPages) { 
            startPage = totalPages - (MAX_VISIBLE_PAGES - 3);
            endPage = totalPages;
        } else { 
            startPage = currentPage - maxPagesBeforeCurrent;
            endPage = currentPage + maxPagesAfterCurrent;
        }
    }
    
    if (startPage > 1) {
        ul.appendChild(createPageElement(1));
        if (startPage > 2) { 
             ul.appendChild(createEllipsisElement());
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        if (i === 1 && startPage > 1) continue; 
        if (i === totalPages && endPage < totalPages) continue; 
        ul.appendChild(createPageElement(i));
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) { 
            ul.appendChild(createEllipsisElement());
        }
        ul.appendChild(createPageElement(totalPages));
    }

    const nextLi = document.createElement('li');
    nextLi.className = `page-item ${currentPage === totalPages ? 'disabled' : ''}`;
    const nextA = document.createElement('a');
    nextA.className = 'page-link';
    nextA.href = '#';
    nextA.textContent = 'Next';
    nextA.addEventListener('click', (e) => {
        e.preventDefault();
        if (currentPage < totalPages) {
            goToPage(currentPage + 1);
        }
    });
    nextLi.appendChild(nextA);
    ul.appendChild(nextLi);

    nav.appendChild(ul);
    container.appendChild(nav);
}

function createPageElement(pageNumber) {
    const li = document.createElement('li');
    li.className = `page-item ${pageNumber === currentPage ? 'active' : ''}`;
    const a = document.createElement('a');
    a.className = 'page-link';
    a.href = '#';
    a.textContent = pageNumber;
    a.addEventListener('click', (e) => {
        e.preventDefault();
        goToPage(pageNumber);
    });
    li.appendChild(a);
    return li;
}

function createEllipsisElement() {
    const li = document.createElement('li');
    li.className = 'page-item disabled';
    const span = document.createElement('span');
    span.className = 'page-link';
    span.textContent = '...';
    li.appendChild(span);
    return li;
}


function goToPage(pageNumber) {
    currentPage = pageNumber;
    renderCurrentPageProblems();
    if (paginationControlsContainerTop) {
        renderPaginationControls(paginationControlsContainerTop);
    }
    if (paginationControlsContainerBottom) {
        renderPaginationControls(paginationControlsContainerBottom);
    }
    window.scrollTo(0, 0); 
}

// --- Initial Rendering ---
document.addEventListener('DOMContentLoaded', () => {
    if (typeof problemsData !== 'undefined' && typeof fileId !== 'undefined') {
        renderCurrentPageProblems();
        if (paginationControlsContainerTop) {
            renderPaginationControls(paginationControlsContainerTop);
        }
        if (paginationControlsContainerBottom) {
            renderPaginationControls(paginationControlsContainerBottom);
        }
    } else {
        console.error("problemsData or fileId is not defined. Check Flask template.");
        if(problemsContainer) problemsContainer.textContent = "Error: Data not loaded.";
    }

    var toastElList = [].slice.call(document.querySelectorAll('.toast'))
    var toastList = toastElList.map(function (toastEl) {
        if (typeof bootstrap !== 'undefined' && typeof bootstrap.Toast === 'function') {
            return new bootstrap.Toast(toastEl)
        }
        return null;
    }).filter(t => t !== null);

    if (typeof renderMathInElement === 'function') {
        renderMathInElement(document.body, {
            delimiters: [
              {left: '$$', right: '$$', display: true},
              {left: '$', right: '$', display: false},
              {left: '\\(', right: '\\)', display: false},
              {left: '\\[', right: '\\]', display: true}
            ],
            output: "htmlAndMathml",
            throwOnError: false
        });
    }
});
