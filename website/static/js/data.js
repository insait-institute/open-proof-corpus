var selectedText = null;
var throwKatexError = false; // global variable to track if there is a KaTeX error

function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            func.apply(this, args);
        }, delay);
    };
}

const debouncedSave = debounce((form, grading_scheme, i, additionalLabels) => {
    saveData(form, grading_scheme, i, additionalLabels);
}, 100); // 500ms delay


// MODIFIED function
function openTab(evt, tabKey, tabGroupIdentifier) {
    // Declare all variables
    var i, tabcontent, tablinks;

    // Get all elements with class="tabcontent" and hide those belonging to the current group
    tabcontent = document.getElementsByClassName("tabcontent");
    for (i = 0; i < tabcontent.length; i++) {
        // Check if the tab content belongs to the current group
        if (tabcontent[i].id.endsWith(`-${tabGroupIdentifier}`)) {
            tabcontent[i].style.display = "none";
        }
    }

    // Get all elements with class="tablinks" in the current group and remove the class "active"
    tablinks = document.getElementsByClassName("tablinks");
    for (i = 0; i < tablinks.length; i++) {
        // Check if the tab link belongs to the current group
        if (tablinks[i].id.includes(`-${tabGroupIdentifier}`)) {
            tablinks[i].className = tablinks[i].className.replace(" active", "");
        }
    }

    // Show the current tab, and add an "active" class to the button that opened the tab
    const currentTabContent = document.getElementById(`tab${tabKey}-${tabGroupIdentifier}`);
    if (currentTabContent) {
        currentTabContent.style.display = "block";
    }
    if (evt && evt.currentTarget) {
        evt.currentTarget.className += " active";
    }
}
// -------------------- Helper Functions --------------------


function handleResponse(response) {
	if (!response.ok) {
		throw new Error('Network response was not ok');
	}
	return response.json();
}

function renderTraceContent(data) {
	const container = document.getElementById("traces");
	renderProblemStatement(data, container);
    let label = document.createElement("h4");
    label.style.fontWeight = "bold";
    label.innerHTML = "Correct Answer";
    container.appendChild(label);
	renderModelOutputs(data.solutions, container, true, data.grading_scheme);
    
    label = document.createElement("h4");
    label.style.fontWeight = "bold";
    label.innerHTML = "Model Outputs";
    container.appendChild(label);
    if (data.solutions.length > 0) {
        renderModelOutputs(data.attempts, container, false, data.grading_scheme, data.problem, data.images,
            data.solutions[0].solution, data.solutions[0].images
        );
    } else {
        renderModelOutputs(data.attempts, container, false, data.grading_scheme, data.problem, data.images);
    }
        
	renderMathInElement(document.body, {
		delimiters: [
            {left: "$$", right: "$$", display: true},
            {left: "$", right: "$", display: false},
            {left: "\\(", right: "\\)", display: false},
            {left: "\\begin{equation}", right: "\\end{equation}", display: true},
            {left: "\\begin{align}", right: "\\end{align}", display: true},
            {left: "\\begin{alignat}", right: "\\end{alignat}", display: true},
            {left: "\\begin{gather}", right: "\\end{gather}", display: true},
            {left: "\\begin{CD}", right: "\\end{CD}", display: true},
            {left: "\\[", right: "\\]", display: true}
        ],
        ignoreHtml: true,
        throwOnError: throwKatexError
	});
}

function renderProblemStatement(data, container) {
	const label = document.createElement("h4");
	label.innerHTML = "Problem";
    label.style.fontWeight = "bold";
    let metadata = [];
    for (let i = 0; i < Object.keys(data.metadata).length; i++) {
        const key = Object.keys(data.metadata)[i];
        const value = data.metadata[key];
        metadata.push({
            label: key,
            value: value
        });
    }
    
	const problemContainer = createProblemBox(data.problem, data.images);

	container.appendChild(label);
    if (metadata.length > 0) {
        const card = addMetaData(metadata);
        container.appendChild(card);
    }

    if (data.issue_other_judge) {
        const issueBox = document.createElement("div");
        issueBox.className = "marked box incorrect-box";
        issueBox.style.whiteSpace = "pre-wrap";
        issueBox.style.tabSize = "4";
        const explanation = document.createElement("p");
        explanation.innerHTML = "<strong>Another judge marked an issue with this problem:</strong> ";
        issueBox.appendChild(explanation);
        issueBox.appendChild(document.createTextNode(data.issue_other_judge.issue));
        const issueContainer = document.createElement("div");
        issueContainer.style.position = "relative";
        issueContainer.appendChild(issueBox);
        container.appendChild(issueContainer);
    }
    
	container.appendChild(problemContainer);

    const form = createProblemFeedbackForm("problem-feedback", "The problem statement is incorrect or incomplete.", 
                                            true, null, data.issue, data.useless, true);
    container.appendChild(form);
}

function createProblemBox(problem, images = null) {
    const problemBox = document.createElement("div");
	problemBox.className = "marked box problem-box";
	problemBox.style.whiteSpace = "pre-wrap";
	problemBox.style.tabSize = "4";
	problemBox.appendChild(document.createTextNode(problem));

	const problemContainer = document.createElement("div");
	problemContainer.style.position = "relative";
    if (images) {
        const gallery = buildImageGallery(images);
        problemBox.appendChild(gallery);
    }
	problemContainer.appendChild(problemBox);
    return problemContainer;
}

function renderModelOutputs(attempts, container, is_gold_answer, grading_scheme, problem = null, 
    problem_images = null, solution = null, solution_images = null
) {
    if (attempts.length === 0) {
        // just show a title saying "No attempts"
        const label = document.createElement("h6");
        label.innerHTML = "No ground-truth solution exists.";
        label.style.fontWeight = "bold";
        // put some extra top and bottom margin
        label.style.marginTop = "1.5rem";
        label.style.marginBottom = "1.5rem";
        container.appendChild(label);
        return;
    }
	let string_text = "normal"
    if (is_gold_answer) {
        string_text = "gold"
    }

    if (attempts.length > 1) {
        const tab = document.createElement("div");
	    tab.className = "tab";
        attempts.forEach((_, i) => {
            const button = document.createElement("button");
            button.className = "tablinks";
            if (is_gold_answer) {
                button.innerHTML = `Solution ${i + 1}`;
            } else {
                button.innerHTML = `Run ${i + 1}`;
            }
            button.id = `tablink${i}-${string_text}`;
            button.onclick = event => openTab(event, i, string_text);
            tab.appendChild(button);
        });
        container.appendChild(tab);
    }
	

	attempts.forEach((output, i) => {
        addSingleOutput(output, container, i, is_gold_answer, grading_scheme, 
            problem, problem_images, solution, solution_images, attempts.length);
	});


	// Show first tab by default
    openTab({currentTarget: document.getElementById(`tablink0-${string_text}`)}, 0, string_text);
}

function addGoldAnswer(content, output, i) {
    let metadata = [];
    for (let i = 0; i < Object.keys(output).length; i++) {
        const key = Object.keys(output)[i];
        if (key == "solution" || key == "images" || key == "run_index" || key == "issue" || key == "issue_other_judge") {
            continue;
        }
        
        const value = output[key];
        metadata.push({
            label: key,
            value: value
        });
    }
    const card = addMetaData(metadata)
    content.appendChild(card);

    if (output.issue_other_judge) {
        const issueBox = document.createElement("div");
        issueBox.className = "marked box incorrect-box";
        issueBox.style.whiteSpace = "pre-wrap";
        issueBox.style.tabSize = "4";
        const explanation = document.createElement("p");
        explanation.innerHTML = "<strong>Another judge marked an issue with this solution:</strong> ";
        issueBox.appendChild(explanation);
        issueBox.appendChild(document.createTextNode(output.issue_other_judge.issue));
        const issueContainer = document.createElement("div");
        issueContainer.style.position = "relative";
        issueContainer.appendChild(issueBox);
        content.appendChild(issueContainer);
    }

    const box = appendSection("", output.solution, "solution-box");
    if (output.images) {
        const gallery = buildImageGallery(output.images);
        box.appendChild(gallery);
    }
    content.appendChild(box);
    const feedback_form = createProblemFeedbackForm("solution-feedback-" + i.toString(), "The solution is incorrect or incomplete.", false, i, output.issue);
    content.appendChild(feedback_form);
}

function shouldShowExistingJudgments(output, grading_scheme) {
    let showExistingJudgmentsOnly = false;
    if (output.grading && output.grading.details && output.grading.details.length === grading_scheme.length) {
        let allPartsDeclareExistingJudgments = true;
        for (let j = 0; j < grading_scheme.length; j++) {
            if (!output.grading.details[j] || !output.grading.details[j].hasOwnProperty('existing_judgments')) {
                allPartsDeclareExistingJudgments = false;
                break;
            }
        }
        if (allPartsDeclareExistingJudgments) {
            showExistingJudgmentsOnly = true;
        }
    }
    return showExistingJudgmentsOnly;
}

function showExistingJudgments(output, grading_scheme) {
    const judgmentsContainer = document.createElement("div");
    judgmentsContainer.className = "existing-judgments-container";
    // Inline styles (padding, margin-top) removed - handled by CSS

    const generalTitle = document.createElement("h4");
    generalTitle.textContent = "Previously Recorded Judgments";
    // Inline styles (fontWeight, marginBottom) removed - handled by CSS
    judgmentsContainer.appendChild(generalTitle);

    for (let j = 0; j < grading_scheme.length; j++) {
        const schemePart = grading_scheme[j];
        const judgmentDetailsArray = output.grading.details[j].existing_judgments;

        const criterionDiv = document.createElement("div");
        criterionDiv.className = "criterion-group"; // Added class
        // Inline style (marginBottom) removed - handled by CSS
        judgmentsContainer.appendChild(criterionDiv);

        const criterionTitle = document.createElement("h5");
        criterionTitle.className = "criterion-title"; // Added class
        criterionTitle.textContent = schemePart.title ?? `Criterion ${j + 1}`;
        // Inline styles (borderBottom, paddingBottom, marginBottom) removed - handled by CSS
        criterionDiv.appendChild(criterionTitle);

        if (judgmentDetailsArray && judgmentDetailsArray.length > 0) {
            judgmentDetailsArray.forEach((judgment, k) => {
                const judgmentBox = document.createElement("div");
                judgmentBox.className = "existing-judgment-box"; // Class changed, 'box' removed
                // Inline styles (marginBottom, padding, border, borderRadius, backgroundColor) removed

                const judgeName = judgment.judge || `Judge ${k + 1}`;
                const judgeHeader = document.createElement("p");
                judgeHeader.className = "judge-header"; // Added class
                judgeHeader.textContent = `${judgeName}'s Assessment:`;
                // Inline styles (fontWeight, color, marginBottom) removed
                judgmentBox.appendChild(judgeHeader);

                const scoreDisplay = document.createElement("p");
                // Inline style (margin) removed
                scoreDisplay.innerHTML = `<strong>Score:</strong> ${judgment.score !== undefined ? judgment.score : 'N/A'} / ${schemePart.points}`;
                judgmentBox.appendChild(scoreDisplay);

                const feedbackDisplay = document.createElement("p");
                // Inline style (margin) removed
                feedbackDisplay.innerHTML = `<strong>Feedback:</strong>`;
                judgmentBox.appendChild(feedbackDisplay);

                const feedbackText = document.createElement("div");
                feedbackText.className = "feedback-text"; // Added class
                feedbackText.textContent = judgment.feedback || 'No feedback provided.';
                // Inline styles (whiteSpace, paddingLeft, fontSize, color) removed
                // white-space: pre-wrap; is now handled by .feedback-text CSS
                judgmentBox.appendChild(feedbackText);

                if (judgment.annotations && judgment.annotations.length > 0) {
                    const annotationsDisplay = document.createElement("p");
                    // Inline style (margin) removed
                    annotationsDisplay.innerHTML = `<strong>Annotations:</strong>`;
                    judgmentBox.appendChild(annotationsDisplay);
                    const annotationsList = document.createElement("ul");
                    annotationsList.className = "annotations-list"; // Added class
                    // Inline style (paddingLeft) removed - handled by CSS
                    judgment.annotations.forEach(annotation => {
                        const annotationItem = document.createElement("li");
                        // add comment and selected_text to the annotation item
                        annotationItem.innerHTML = `<strong>Selected Text:</strong> ${annotation.selected_text}<br><strong>Comment:</strong> ${annotation.comment}`;
                        annotationsList.appendChild(annotationItem);
                    });
                    judgmentBox.appendChild(annotationsList);
                }

                criterionDiv.appendChild(judgmentBox);
            });
        } else {
            const noJudgmentsText = document.createElement("p");
            noJudgmentsText.className = "no-judgments-message"; // Added class
            noJudgmentsText.textContent = "No existing judgments recorded for this criterion.";
            // Inline style (fontStyle) removed
            criterionDiv.appendChild(noJudgmentsText);
        }
    }
    return judgmentsContainer;
}


function addModelOutput(content, output, i, grading_scheme,
    ground_truth_solution_text = null, // Renamed for clarity
    ground_truth_solution_images = null) { // Renamed for clarity

    const twoColumnWrapper = document.createElement("div");
    twoColumnWrapper.style.display = "flex";
    twoColumnWrapper.style.gap = "0"; // gap handled by resizer width
    twoColumnWrapper.style.alignItems = "stretch";
    twoColumnWrapper.className = "two-col-wrapper";

    // ---- Main box (Model's own solution) ----
    const mainBox = document.createElement("div");
    mainBox.id = `model-solution-main-${i}`;
    mainBox.className = "marked box response-box"; // Model's own solution
    mainBox.style.whiteSpace = "pre-wrap";
    mainBox.style.tabSize = "4";
    mainBox.style.flex = "0 0 68%"; // Default split
    mainBox.style.minHeight = "500px";
    // Clean up LaTeX common errors for model output
    let modelSolutionText = output.solution;
    let allMarkers = []

    // --- Marker Injection Logic ---
    if (output.llm_judgment && output.llm_judgment.result && output.llm_judgment.result.issues) {
        output.llm_judgment.result.issues = output.llm_judgment.result.issues.map((issue, index) => ({ ...issue, originalIssueIndex: index }))
        const issues = output.llm_judgment.result.issues;
        const targetableIssues = issues
            .filter(issue => issue.start_index !== null && issue.start_index !== undefined);

        const length = targetableIssues.length;
        for (let j = 0; j < length; j++) {
            let end_index = targetableIssues[j].start_index + targetableIssues[j].text.length;
            if (targetableIssues[j].end_index !== null &&
                targetableIssues[j].end_index !== undefined) {
                end_index = targetableIssues[j].end_index;
            }
            targetableIssues.push({
                start_index: end_index,
                text: "",
                originalIssueIndex: targetableIssues[j].originalIssueIndex,
                is_end: true,
            })
        }
        // Sort issues by start_index in DESCENDING order to insert markers
        // from the end of the string backwards. This prevents prior insertions
        // from affecting the indices of subsequent insertions.
        targetableIssues.sort((a, b) => b.start_index - a.start_index);

        const kaTeXDelimiters = [ // For identifying math environments
            { open: '$', close: '$', type: 'inline' }, // Must be before $$
            { open: '$$', close: '$$', type: 'display' },
            { open: '\\(', close: '\\)', type: 'inline' },
            { open: '\\[', close: '\\]', type: 'display' }
        ];

        targetableIssues.forEach(issue => {
            let resolvedInsertionPoint = issue.start_index;
            const markerId = `llm-issue-target-${i}-${issue.originalIssueIndex}`;
            let markerString = `|||${markerId}|||`;
            if (issue.is_end) {
                // If this is an end marker, we need to adjust the insertion point
                // to be just after the end of the issue text.
                markerString = `///${markerId}///`
            }

            // Heuristic to check if start_index is inside a math environment
            // and adjust insertion point to be *before* that environment.
            for (const delim of kaTeXDelimiters) {
                let searchFrom = 0;
                let foundEnvForThisIssue = false;
                while (searchFrom < modelSolutionText.length) {
                    const openPos = modelSolutionText.indexOf(delim.open, searchFrom);
                    if (openPos === -1) break; // No more of this delimiter

                    // Basic escape check (e.g. \\$ or \\\[ should be ignored)
                    if (openPos > 0 && modelSolutionText[openPos - 1] === '\\') {
                        let k = openPos - 1; let slashes = 0;
                        while (k >= 0 && modelSolutionText[k] === '\\') { slashes++; k--; }
                        if (slashes % 2 === 1) { // Odd number of slashes -> escaped
                            searchFrom = openPos + delim.open.length;
                            continue;
                        }
                    }
                    
                    // Need to find a non-nested closing delimiter. This simplified indexOf is not robust for nested LaTeX.
                    // For this specific marker task, we're checking if start_index falls within *any* identified block.
                    const closePos = modelSolutionText.indexOf(delim.close, openPos + delim.open.length);
                    if (closePos === -1) { // Unclosed environment
                        searchFrom = openPos + delim.open.length; // Try to skip malformed part
                        continue;
                    }

                    // If issue.start_index is within this math environment [openPos, closePos + delim.close.length]
                    if (issue.start_index >= openPos && issue.start_index < (closePos + delim.close.length)) {
                        if (issue.is_end) {
                            resolvedInsertionPoint = closePos + delim.close.length; // Place marker *after* this math environment
                        } else {
                            resolvedInsertionPoint = openPos; // Place marker *before* this math environment
                        }
                        foundEnvForThisIssue = true;
                        break; 
                    }
                    searchFrom = closePos + delim.close.length; // Continue search after this environment
                }
                if (foundEnvForThisIssue) break;
            }

            // as long as the insertion point -1 contains an alphanumeric character, move it back
            if (issue.is_end) {
                while (resolvedInsertionPoint < modelSolutionText.length &&
                    (modelSolutionText[resolvedInsertionPoint].match(/[a-zA-Z0-9]/))) {
                    resolvedInsertionPoint++;
                }
            } else {
                while (resolvedInsertionPoint > 0 &&
                    (modelSolutionText[resolvedInsertionPoint - 1].match(/[a-zA-Z0-9]/))) {
                    resolvedInsertionPoint--;
                }
            }
            
            // Clamp insertion point
            resolvedInsertionPoint = Math.max(0, Math.min(resolvedInsertionPoint, modelSolutionText.length));

            modelSolutionText =
            modelSolutionText.substring(0, resolvedInsertionPoint) +
                markerString +
                modelSolutionText.substring(resolvedInsertionPoint);
            if (!issue.is_end) {
                allMarkers.push(markerId); // Collect all marker IDs for later replacement
            }
        });
    }

    modelSolutionText = modelSolutionText.replaceAll("\\\\[", "\\[").replaceAll("\\\\]", "\\]");
    modelSolutionText = modelSolutionText.replaceAll("\\\\(", "\\(").replaceAll("\\\\)", "\\)");
    modelSolutionText = modelSolutionText.replaceAll("\\[2mm]", "\\\\");
    // Basic check for unpaired $ - you might want more robust parsing
    if ((modelSolutionText.match(/\$/g) || []).length % 2 !== 0) {
        modelSolutionText = modelSolutionText.replaceAll("\\(", "$").replaceAll("\\)", "$");
    }
    // prepare the text node so that its innerHTML can be set later
    textNode = document.createElement("span");
    textNode.textContent = modelSolutionText; // Placeholder for markers
    // If there are markers, replace them with spans with the marker ID
    if (allMarkers.length > 0) {
        allMarkers.forEach(markerId => {
            const markerSpan = document.createElement("span");
            markerSpan.id = markerId;
            textNode.innerHTML = textNode.innerHTML.replace(`|||${markerId}|||`, markerSpan.outerHTML.substring(0, markerSpan.outerHTML.length - 7));
            textNode.innerHTML = textNode.innerHTML.replace(`///${markerId}///`, "</span>");
        });
    }
    mainBox.appendChild(textNode);
    twoColumnWrapper.appendChild(mainBox);

    // ---- Resizer ----
    const resizer = document.createElement("div");
    resizer.className = "column-resizer";
    twoColumnWrapper.appendChild(resizer);

    // ---- Secondary box (LLM Judgment or Ground Truth) ----
    let secondaryBox;
    if (output.llm_judgment) {
        secondaryBox = createLlmJudgmentPanel(output.llm_judgment.result, i);
    // The createLlmJudgmentPanel already sets necessary styles like flex, minHeight
    } else if (ground_truth_solution_text !== null) {
        secondaryBox = document.createElement("div");
        secondaryBox.className = "marked box solution-box"; // Ground-truth solution
        secondaryBox.style.whiteSpace = "pre-wrap";
        secondaryBox.style.tabSize = "4";
        secondaryBox.style.flex = "0 0 30%";
        secondaryBox.style.minHeight = "500px";
        // Clean up LaTeX for ground truth text as well
        let truthText = ground_truth_solution_text;
        truthText = truthText.replaceAll("\\\\[", "\\[").replaceAll("\\\\]", "\\]");
        truthText = truthText.replaceAll("\\\\(", "\\(").replaceAll("\\\\)", "\\)");
        truthText = truthText.replaceAll("\\[2mm]", "\\\\");
        if ((truthText.match(/\$/g) || []).length % 2 !== 0) {
            const length = truthText.length;
            truthText = truthText.replaceAll("\\(", "$").replaceAll("\\)", "$");
            if (truthText.length < length) {
                console.warn("Corrected unpaired LaTeX delimiters in ground-truth:", ground_truth_solution_text);
            }
        }
        secondaryBox.appendChild(document.createTextNode(truthText));

        if (ground_truth_solution_images) {
            const gallery = buildImageGallery(ground_truth_solution_images);
            secondaryBox.appendChild(gallery);
        }
    }

    if (output.llm_judgment || ground_truth_solution_text !== null) {
        twoColumnWrapper.appendChild(secondaryBox);
        enableColumnResize(twoColumnWrapper, mainBox, resizer, secondaryBox);
        content.appendChild(twoColumnWrapper);
    } else {
        mainBox.style.flex = "0 0 100%"; // Default split
        content.appendChild(mainBox);
    }


    // --- Existing logic for grading form, annotations, and save button ---
    // This part should remain mostly the same.
    if (shouldShowExistingJudgments(output, grading_scheme)) {
        const judgmentsContainer = showExistingJudgments(output, grading_scheme);
        content.appendChild(judgmentsContainer);
    } else {
        const form = document.createElement("form");
        form.className = "needs-validation d-flex flex-column gap-3";
        for (let j = 0; j < grading_scheme.length; j++) {
            let currentGradingForPart = {};
            if (output.grading && output.grading.details && output.grading.details[j]) {
                currentGradingForPart = { ...output.grading.details[j] };
                delete currentGradingForPart.existing_judgments;
            }
            createGradingForm(form, grading_scheme[j], i, grading_scheme, currentGradingForPart);
        }

        let additionalLabelsForSave = null;
        if (output.grading) {
            additionalLabelsForSave = addFormFinalElements(form, i, output.grading["uncertain"],
            output.grading["no_feedback"], output.grading["long"], output.annotations, grading_scheme);
        } else {
            additionalLabelsForSave = addFormFinalElements(form, i, false, false, false, // Added 'long' default
            output.annotations, grading_scheme);
        }
        addSaveButton(form, grading_scheme, i, additionalLabelsForSave);
        content.appendChild(form);
    }
}

function addSingleOutput(output, container, i, is_gold_answer, grading_scheme, problem = null,
    problem_images = null, solution = null, solution_images = null, attempt_length = 1
) {
    if (!is_gold_answer && output.rejected) {
        return; // skip rejected attempts
    }

    const content = document.createElement("div");
    const tabGroupForContent = is_gold_answer ? 'gold' : 'normal';
    content.id = `tab${i}-${tabGroupForContent}`; // Use the correct group
    if (attempt_length > 1) {
        content.className = "tabcontent";
    }
    
    if (problem) {
        const problemContainer = createProblemBox(problem, problem_images);
        content.appendChild(problemContainer);
    }
    output.run_index = i; // Attach for later grading tab logic

    if (is_gold_answer) {
        addGoldAnswer(content, output, i);
    } else {
        addModelOutput(content, output, i, grading_scheme, solution, solution_images);
    }
    container.appendChild(content);
}


function addMetaData(meta_data_list) {
    const card = document.createElement("div");
    card.className = "meta-card";
    for (let i = 0; i < meta_data_list.length; i++) {
        const meta_data = meta_data_list[i];
        const metaP   = document.createElement("p");
        const metaLbl = document.createElement("span");
        metaLbl.className = "label";
        metaLbl.textContent = `${meta_data.label}: `;     // bolded by CSS
        metaP.appendChild(metaLbl);
        if (meta_data.label == "url") {
            const metaLink = document.createElement("a");
            metaLink.href = meta_data.value;
            metaLink.textContent = meta_data.value;
            metaLink.target = "_blank";
            metaP.appendChild(metaLink);
        } else if (typeof meta_data.value == "object" && meta_data.value.length > 1) {
            const metaList = document.createElement("ul");
            metaList.style.marginBottom = "0rem";
            for (let j = 0; j < meta_data.value.length; j++) {
                const metaListItem = document.createElement("li");
                metaListItem.textContent = meta_data.value[j];
                metaList.appendChild(metaListItem);
            }
            metaP.appendChild(metaList);
        } else {
            const val = document.createTextNode(`${meta_data.value}`)
            metaP.appendChild(val);
        }
        card.appendChild(metaP);
    }
    return card;
}

/**
 * Create and append a multiple-choice question node.
 *
 * @param {HTMLElement} container   – Where the whole block should be appended.
 * @param {string}      question    – The text of the question.
 * @param {string[]}    possibilities – Array of answer strings.
 * @param {string}      name        – (Unique) name used to group the radios.
 *
 */
function addMultipleChoice(question, possibilities, name, defaultValue = null) {
    // a <fieldset> groups the question and its options semantically
    const wrapper = document.createElement('fieldset');
    wrapper.className = 'mb-3';           // keep Bootstrap spacing if present

    // the “question” line
    const legend = document.createElement('legend');
    legend.className = 'col-form-label pt-0'; // bootstrap-friendly
    legend.textContent = question;
    wrapper.appendChild(legend);

    // create one radio/label pair for each possible answer
    const radios   = [];
    const labels   = [];

    possibilities.forEach((text, idx) => {
        const id = `${name}-${idx}`;

        const radio = document.createElement('input');
        radio.type      = 'radio';
        radio.className = 'form-check-input';
        radio.id        = id;
        radio.name      = name;
        radio.value     = text;

        const lbl = document.createElement('label');
        lbl.className   = 'form-check-label';
        lbl.htmlFor     = id;
        lbl.style.marginLeft = '0.5rem';
        lbl.textContent = text;

        // wrap each pair so they sit nicely on one line
        const pair = document.createElement('div');
        pair.className   = 'form-check';
        pair.style.display      = 'inline-flex';
        pair.style.alignItems   = 'center';
        pair.style.marginRight  = '1rem';

        if (defaultValue && defaultValue === text) {
            radio.checked = true;
        }

        pair.append(radio, lbl);
        wrapper.appendChild(pair);

        radios.push(radio);
        labels.push(lbl);
    });

    return wrapper;
}

function addCheckbox(form, id, label, checked, i=null, grading_scheme=null) {
    const cb = document.createElement('input');
    cb.type  = 'checkbox';
    cb.id    = id;
    cb.name  = id;
    cb.className = 'form-check-input';
    if (checked) {
        cb.checked = true;
    }

    cb.addEventListener('change', () => {
        if (grading_scheme) {
            debouncedSave(form, grading_scheme, i, null);
        }
        // if the checkbox is checked, show the feedback textarea
    });

    // create the label
    const lbl = document.createElement('label');
    lbl.htmlFor   = 'uncertain-checkbox';
    lbl.className = 'form-check-label';
    lbl.style.marginLeft = '0.5rem';
    lbl.textContent = label;

    // wrap them in a div that forces inline layout
    const wrapper = document.createElement('div');
    wrapper.className = 'form-check';          // keep the Bootstrap look
    wrapper.style.display = 'inline-flex';     // sit input & label on one line
    wrapper.style.alignItems = 'center';       // vertical alignment

    wrapper.append(cb, lbl);
    form.appendChild(wrapper);       
    return {
        checkbox: cb,
        label: lbl,
        wrapper: wrapper
    }          // add to your <form>
}

function createSaveButton(id) {
    /* 1.  Build a little flex row ---------------------------------- */
    const wrapper = document.createElement("div");
    const actionGroup = document.createElement("div");
    actionGroup.className = "d-inline-flex align-items-center gap-2";  
    // wrapper.style.marginTop = "-1rem"; // add some space above the button
    wrapper.appendChild(actionGroup);
    //  – d-inline-flex → stays on the same line as the rest of the form
    //  – align-items-center → vertical centering
    //  – gap-2 → a small space between button and pill

    /* 2.  Create the button --------------------------------------- */
    const saveBtn = document.createElement("button");
    saveBtn.type = "button";                      // no form submit
    saveBtn.className = "btn btn-primary";
    saveBtn.textContent = "Save";

    /* 3.  Create the status pill ---------------------------------- */
    const statusPill = document.createElement("span");
    statusPill.id = "status-form-" + id;
    statusPill.className = "badge d-none fade";   // keeps fade-in/out utilities
    actionGroup.append(saveBtn, statusPill);      // put them inside the wrapper
    return {
        actionGroup: wrapper,
        saveBtn: saveBtn,
        statusPill: statusPill
    }
}

function addFormFinalElements(form, i, uncertain, no_feedback, long, annotations, grading_scheme) {
    // add h6 "Annotations"
    const annotationLabel = document.createElement("h6");
    annotationLabel.innerHTML = "Annotations";
    annotationLabel.style.fontWeight = "bold";

    const annotationsOverviewBox = document.createElement("div");

    const emptyLabel = addAnnotations(annotations, annotationsOverviewBox, i);

    form.appendChild(annotationLabel);
    form.appendChild(annotationsOverviewBox);
    // add a button "+ add annotation"
    const addAnnotationBtn = document.createElement("button");
    addAnnotationBtn.type = "button";
    addAnnotationBtn.className = "btn btn-secondary";
    addAnnotationBtn.textContent = "+ Add annotation (select text in model answer before adding)";
    
    /* -------- Feedback textarea for annotation ------- */
    const feedbackGroup = document.createElement("div");
    feedbackGroup.className = "d-none flex-column gap-2"; // hidden until checked

    const feedbackLabel = document.createElement("label");
    feedbackLabel.className = "form-label fw-semibold";
    feedbackLabel.textContent = "Annotation";
    feedbackLabel.htmlFor = `annotation-${crypto.randomUUID()}`;
    

    const feedbackInput = document.createElement("textarea");
    feedbackInput.className = "form-control";
    feedbackInput.name = `annotation`;
    feedbackInput.id   = feedbackLabel.htmlFor;
    feedbackInput.rows = 3;
    feedbackInput.placeholder = "Describe annotation...";
    feedbackInput.style.marginBottom = "1rem";
    
    feedbackGroup.appendChild(feedbackLabel);
    feedbackGroup.appendChild(feedbackInput);
    
    addAnnotationBtn.onclick = () => {
        selectedText = getSelectedText();
        if (selectedText) {
            feedbackLabel.textContent = "Annotation: " + selectedText.selectedText;
            feedbackGroup.classList.remove("d-none");
            feedbackInput.focus();
        }
    }
    form.appendChild(addAnnotationBtn);
    form.appendChild(feedbackGroup);

    // Add a checkbox for "I am uncertain about my judgment"
    // create the checkbox
    addCheckbox(form, "uncertain-checkbox", "I am uncertain about my judgment.", uncertain, i, grading_scheme);
    addCheckbox(form, "no-feedback-checkbox", "I do not have the necessary background to grade this solution (will be assigned to other judge).", no_feedback, i, grading_scheme);
    addCheckbox(form, "long-checkbox", "This solution is very tedious, long, and/or incomprehensible. I cannot judge this (will not be assigned to other judge)", long, i, grading_scheme);
    return {
        emptyLabel: emptyLabel,
        annotationsOverviewBox: annotationsOverviewBox,
        feedbackGroup: feedbackGroup,
        feedbackInput: feedbackInput
    };
}

async function saveData(form, grading_scheme, i, 
                        additionalLabels=null, finalRow=null) {
    // get all data in the form
    const formData = new FormData(form);
    const data = [];
    const uncertain_data = {};
    let annotation = {};
    for (let l = 0; l < grading_scheme.length; l++) {
        data.push({
            "part_id": grading_scheme[l].part_id,
        });
    }
    for (const [key, value] of formData.entries()) {
        if (key == "uncertain-checkbox") {
            uncertain_data["uncertain"] = value;
            continue;
        } else if (key == "no-feedback-checkbox") {
            uncertain_data["no_feedback"] = value;
            continue;
        } else if (key == "long-checkbox") {
            uncertain_data["long"] = value;
        } else if (key == "annotation") {
            if (value.length > 0) {
                annotation = {
                    "comment": value,
                    "selected_text": selectedText.selectedText,
                    "n_equations": selectedText.n_equations,
                    "n_equations_before": selectedText.n_equations_before,
                    "id": crypto.randomUUID()
                };
                if (additionalLabels) {
                    addAnnotation(annotation.selected_text, annotation.comment, 
                        annotation.id, additionalLabels.annotationsOverviewBox, i, 
                        additionalLabels.emptyLabel);
                }
                
            }
            continue;
        }
        let [name, part_id] = key.split("-");
        part_id = parseInt(part_id);
        for (let j = 0; j < data.length; j++) {
            if (data[j].part_id == part_id) {
                data[j][name] = value;
                if (name == "score") {
                    data[j].score = parseFloat(value);
                }
            }
        }
    }
    postprocessGrading(data, uncertain_data, i, data.useless);
    // send data to server
    fetch(`/${judge_id}/save_grading/`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            "data": data,
            "uncertain": uncertain_data,
            "annotation": annotation,
            "file_name": file_name,
            "run_index": i
        })
    }).then(
        response => {
            if (finalRow) {
                updateStatus(response, finalRow.statusPill);
                if (additionalLabels) {
                    additionalLabels.feedbackGroup.classList.add("d-none");
                    additionalLabels.feedbackInput.value = "";
                }
            }
        }
    ).catch(
        error => {
            if (finalRow) {
                finalRow.statusPill.textContent = "Error saving grading!";
                finalRow.statusPill.classList.remove("d-none", "bg-success");
                finalRow.statusPill.classList.add("bg-danger"); 
            }
        }
    )
}

function addSaveButton(form, grading_scheme, i, additionalLabels) {
    const finalRow = createSaveButton("grading")
    // (add px-2 py-1 text-white etc. if you want padding/colours)

    /* 4.  Assemble and attach ------------------------------------- */
    form.appendChild(finalRow.actionGroup);      
    
    finalRow.saveBtn.onclick = () => {
        saveData(form, grading_scheme, i, additionalLabels, finalRow);
    };
}

function addAnnotations(annotations, node, i) {
    const label = document.createElement("p");
    label.innerHTML = "No annotations have been added yet. To add an annotation, first select the text in the model answer and then click on the button below.";
    label.className = "d-none";
    node.appendChild(label);
    if (!annotations || annotations.length === 0) {
        // add simple message that no annotation has been added yet
        label.classList.remove("d-none");
        return label;
    } else {
        for (let index = 0; index < annotations.length; index++) {
            const annotation = annotations[index];
            addAnnotation(annotation.selected_text, annotation.comment, annotation.id, node, i, label);
        }
    }
    return label;
}

function addAnnotation(selected_text, comment, annotation_id, node, i, empty_label) {
    /*  ────────── wrapper ────────── */
    const wrapper = document.createElement("div");
    wrapper.classList.add(
        "d-flex",               // horizontal layout (flexbox)
        "justify-content-between",
        "align-items-start",
        "p-2",                  // a little padding
        "mb-2",                 // gap beneath each annotation
        "bg-light",             // light-grey background (Bootstrap)
        "rounded",              // soft corners
        "annotation-box"        // custom hook if you want extra CSS
    );

    /*  ────────── text block ────────── */
    const textBlock = document.createElement("div");
    textBlock.innerHTML = `
        <p class="mb-1">
            <strong>Selected Text:</strong> ${selected_text}
        </p>
        <p class="mb-0">
            <strong>Comment:</strong> ${comment}
        </p>
    `;

    /*  ────────── close (“×”) button ────────── */
    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.classList.add("btn", "btn-sm", "btn-outline-secondary", "ms-3");
    closeBtn.innerHTML = "❌";
    closeBtn.setAttribute("aria-label", "Remove annotation");
    empty_label.classList.add("d-none");

    closeBtn.addEventListener("click", () => {
        /* 1️⃣  Tell the back-end to delete the entry  */
        fetch(`/${judge_id}/remove_annotation/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                annotation_id: annotation_id, // global
                file_name: file_name,   // global
                run_index: i            // global
            })
        });

        /* 2️⃣  Hide this annotation in the UI        */
        wrapper.classList.add("d-none");
        // if all annotations are hidden, show the empty label
        const annotations = document.getElementsByClassName("annotation-box");
        let allHidden = true;
        for (let i = 0; i < annotations.length; i++) {
            if (!annotations[i].classList.contains("d-none")) {
                allHidden = false;
                break;
            }
        }
        if (allHidden) {
            empty_label.classList.remove("d-none");
        }
    });

    /*  ────────── assemble & attach ────────── */
    wrapper.appendChild(textBlock);
    wrapper.appendChild(closeBtn);
    node.appendChild(wrapper);
}

async function updateStatus(response, pill) {
    var status = "ok"
    if (!response.ok) {
        status = "Server error"
    } else {
        const json = await handleResponse(response);
        status = json.status;
    }
    
    // update text + colour
    pill.classList.remove("bg-success", "bg-danger");
    if (status === "success") {
      pill.textContent = "Saved ✓";
      pill.classList.add("bg-success");
    } else {
      pill.textContent = `Validation failed! (${status})`;
      pill.classList.add("bg-danger");
    }
  
    /* ---------- FADE-IN ---------- */
    pill.classList.remove("d-none");        // put it back in the flow
    pill.offsetWidth;                       // <- force a reflow (gap)
    pill.classList.add("show");             // triggers opacity → 1
  
    /* ---------- FADE-OUT ---------- */
    setTimeout(() => {
      pill.classList.remove("show");        // opacity → 0
      pill.addEventListener("transitionend", function handler() {
        pill.classList.add("d-none");       // hide after fade finishes
        pill.removeEventListener("transitionend", handler);
      });
    }, 3000);
  }

function check_sidebar_status(grading, uncertain_data, useless = false) {
    let finished = 2
    if (useless) {
        return 2;
    }
    if (uncertain_data.no_feedback || uncertain_data.long) {
        return finished;
    }
    for (i = 0; i < grading.length; i++) {
        if (grading[i].feedback === "" || isNaN(grading[i].score)) {
            finished = 1;
            break;
        }
    }
    return finished;
}

function postprocessGrading(data, uncertain_data, run_index, useless = false) {
    raw_file_data["attempts"][run_index].grading = data;
    // update sidebar_info
    for (i = 0; i < sidebar_info.file_names.length; i++) {
        if (sidebar_info.file_names[i] == file_name) {
            
            sidebar_info.finished[i][run_index] = check_sidebar_status(data, uncertain_data, useless);
            break;
        }
    }
    // update sidebar
    addFileNamesToSidebar(sidebar_info, file_name);
}


function appendSection(
    title,
    text,
    className,
    secondaryText = null,
    secondaryImages = null,
    secondaryClassName = ""
) {
    /* ---------- wrapper ---------- */
    // replace "\\[" with "\[" and "\\]" with "\]"
    text = text.replaceAll("\\\\[", "\\[").replaceAll("\\\\]", "\\]");
    text = text.replaceAll("\\\\(", "\\(").replaceAll("\\\\)", "\\)");
    // so common I delete it
    text = text.replaceAll("\\[2mm]", "\\\\");
    const countSubstrings = (str, searchValue) => {
        let count = 0,
          i = 0;
        while (true) {
          const r = str.indexOf(searchValue, i);
          if (r !== -1) [count, i] = [count + 1, r + 1];
          else return count;
        }
      };
    if (countSubstrings(text, "$") % 2 !== 0) {
        // model sometimes doesnt pair brackets well
        const length = text.length;
        text = text.replaceAll("\\(", "$").replaceAll("\\)", "$");
        if (text.length < length) {
            console.warn("Removed unpaired brackets from text:", text);
            // throwKatexError = true; // enable error throwing
        }
    }
    
    // 
    const wrapper = document.createElement("div");
    wrapper.style.display    = "flex";
    wrapper.style.gap        = "0";           // gap handled by resizer width
    wrapper.style.alignItems = "stretch";
    wrapper.className        = "two-col-wrapper";

    /* ---------- optional title ---------- */
    if (title !== "") {
        const label = document.createElement("h4");
        label.textContent  = title;
        label.style.fontWeight = "bold";
        wrapper.appendChild(label);
        // let the title span both columns
        label.style.flex = "1 0 100%";
    }

    /* ---------- main box ---------- */
    const mainBox = document.createElement("div");
    mainBox.className  = `marked box ${className}`;
    mainBox.style.whiteSpace = "pre-wrap";
    mainBox.style.tabSize    = "4";
    mainBox.style.flex       = secondaryText ? "0 0 68%" : "0 0 100%";
    if (secondaryText) {
        mainBox.style.minHeight  = "500px";
    }
    
    mainBox.appendChild(document.createTextNode(text));
    wrapper.appendChild(mainBox);

    /* ---------- only build the second column (and resizer) when needed ---------- */
    if (secondaryText !== null) {

        /* ---- resizer ---- */
        const resizer = document.createElement("div");
        resizer.className = "column-resizer";
        // the resizer must be between the two boxes
        wrapper.appendChild(resizer);

        /* ---- secondary box ---- */
        const secondaryBox = document.createElement("div");
        secondaryBox.className  = `marked box ${secondaryClassName}`;
        secondaryBox.style.whiteSpace = "pre-wrap";
        secondaryBox.style.tabSize    = "4";
        secondaryBox.style.flex       = "0 0 30%";
        secondaryBox.style.minHeight  = "500px";
        secondaryBox.appendChild(document.createTextNode(secondaryText));

        /* optional images */
        if (Array.isArray(secondaryImages)) {
            secondaryImages.forEach(src => {
                const img = new Image();
                img.src = src;
                img.style.maxWidth = "100%";
                img.style.display  = "block";
                secondaryBox.appendChild(img);
            });
        }

        wrapper.appendChild(secondaryBox);

        /* ---- activate drag to resize ---- */
        enableColumnResize(wrapper, mainBox, resizer, secondaryBox);
    }

    return wrapper;
}

/**
 * Makes two flex children resizable by dragging the divider in between.
 * Uses pixel widths to stay immune to later wrapper growth.
 */
function enableColumnResize(wrapper, leftBox, resizer, rightBox) {
    const MIN_LEFT  = 200;   // px
    const MIN_RIGHT = 200;   // px

    resizer.addEventListener("pointerdown", startDrag);

    function startDrag(e) {
        e.preventDefault();
        document.body.classList.add("resize-active");
        resizer.setPointerCapture(e.pointerId);
        document.addEventListener("pointermove", onDrag);
        document.addEventListener("pointerup",   stopDrag);
    }

    function onDrag(e) {
        const wrapperRect = wrapper.getBoundingClientRect();
        const total = wrapperRect.width - resizer.offsetWidth - 20;

        // distance from the wrapper’s left edge to the pointer
        let leftPx = e.clientX - wrapperRect.left;

        // clamp so neither box disappears
        leftPx = Math.max(MIN_LEFT, Math.min(total - MIN_RIGHT, leftPx));

        // set fixed pixel flex-basis on both sides
        leftBox.style.flex  = `0 0 ${leftPx}px`;
        rightBox.style.flex = `0 0 ${total - leftPx}px`;
    }

    function stopDrag(e) {
        document.body.classList.remove("resize-active");
        resizer.releasePointerCapture(e.pointerId);
        document.removeEventListener("pointermove", onDrag);
        document.removeEventListener("pointerup",   stopDrag);
    }
}

/**
 * Build a grading form.
 * @param {Object} scheme – e.g. {title, description, points}
 * @param {Object} grading – e.g. {score, feedback}
 * @param {Function} onSave  – callback({score, feedback})            (optional)
 * @returns {HTMLFormElement}
 */
function createGradingForm(form, scheme, i, grading_scheme, grading = {}) {
    // ── title & description ───────────────────────────────────────
    // ── title & description ───────────────────────────────────────
    const title = document.createElement("h5");
    title.textContent = scheme.title ?? "Untitled criterion";
    // set lower bottom margin
    title.style.marginBottom = "-0.5rem";
    form.appendChild(title);

    const desc = document.createElement("p");
    desc.className = "text-muted mb-1"; // Assuming this class comes from your setup (e.g., Bootstrap)
    desc.innerHTML = scheme.description ?? "";
    desc.style.display = "none"; // Initially hide the description

    const toggleButton = document.createElement("button");
    toggleButton.textContent = "Show Instructions "; // Added a space for the arrow
    toggleButton.className = "toggle-description-button"; // Dedicated class for styling

    // Create an element for the arrow
    const arrowSpan = document.createElement("span");
    arrowSpan.className = "arrow-indicator";
    arrowSpan.innerHTML = "&#9660;"; // Downward pointing triangle (▼)
    toggleButton.appendChild(arrowSpan);

    toggleButton.addEventListener("click", (e) => {
        const isHidden = desc.style.display === "none";
        desc.style.display = isHidden ? "block" : "none";
        toggleButton.childNodes[0].nodeValue = isHidden ? "Hide Instructions " : "Show Instructions "; // Update text node
        arrowSpan.innerHTML = isHidden ? "&#9650;" : "&#9660;"; // Up (▲) or Down (▼)
        e.preventDefault(); // Prevent default button behavior
    });

    form.appendChild(toggleButton);
    form.appendChild(desc);

    // ── score input group ─────────────────────────────────────────
    const scoreDiv = document.createElement("div");
    scoreDiv.className = "mb-2";

    const scoreLabel = document.createElement("label");
    scoreLabel.className = "form-label fw-semibold";
    scoreLabel.textContent = `Score (0 - ${scheme.points})`;
    scoreLabel.htmlFor = `score-${crypto.randomUUID()}`;

    const scoreInput = document.createElement("input");
    scoreInput.id    = scoreLabel.htmlFor;
    scoreInput.type  = "number";
    scoreInput.min   = "0";
    scoreInput.max   = String(scheme.points);
    if (scheme.integer) {
        scoreInput.step  = "1";
    } else {
        scoreInput.step  = "0.1"; // allow decimals
    }
    scoreInput.value = grading.score ?? "";
    scoreInput.placeholder = grading.score ?? `0 - ${scheme.points}`;
    scoreInput.className = "form-control";
    scoreInput.name = "score-" + scheme.part_id;      //  ← add this
    scoreInput.addEventListener('input', () => {
        const n = Number(scoreInput.value);
        const isInt = Number.isInteger(n);
        const int_required = scheme.integer ?? true; // default to false if not specified
        if (!isInt && int_required) {
            scoreInput.setCustomValidity('Whole numbers only, please.');
        } else if(!int_required) {
            scoreInput.setCustomValidity('');
            debouncedSave(form, grading_scheme, i, null)
        }
        scoreInput.reportValidity();
    });

    scoreDiv.appendChild(scoreLabel);
    scoreDiv.appendChild(scoreInput);
    form.appendChild(scoreDiv);

    // ── feedback textarea ─────────────────────────────────────────
    const fbDiv = document.createElement("div");
    fbDiv.className = "mb-2";

    const fbLabel = document.createElement("label");
    fbLabel.className = "form-label fw-semibold";
    fbLabel.textContent = "Feedback";
    fbLabel.htmlFor = `feedback-${crypto.randomUUID()}`;
    const fbInput = document.createElement("textarea");
    fbInput.id   = fbLabel.htmlFor;
    fbInput.rows = 3;
    fbInput.placeholder = grading.feedback ?? "Enter feedback...";
    fbInput.value = grading.feedback ?? "";
    fbInput.className = "form-control";
    fbInput.name = "feedback-" +  scheme.part_id;      //  ← and this
    fbInput.addEventListener('input', () => {
        debouncedSave(form, grading_scheme, i, null)
    });

    fbDiv.appendChild(fbLabel);
    fbDiv.appendChild(fbInput);
    form.appendChild(fbDiv);
  
    return form;
  }

/**
 * Build a two-row gallery from {label:url}.
 * @param {Object} figures           – mapping label → image URL
 * @param {string|HTMLElement} mount – where to inject the gallery (default body)
 */
function buildImageGallery(figures){
    /* ---------- create / mount containers ---------- */
    const gallery  = document.createElement('div');
    gallery.className = 'gallery';
  
    // create the overlay once
    let lightbox = document.getElementById('lightbox');
    if (!lightbox){
      lightbox = document.createElement('div');
      lightbox.id = 'lightbox';
      lightbox.innerHTML = '<img alt="full size">';
      document.body.appendChild(lightbox);
    }
    const lightImg = lightbox.querySelector('img');
  
    /* ---------- thumbnails ---------- */
    Object.entries(figures).forEach(([label, src])=>{
      const fig = document.createElement('figure');
      fig.className = 'figure';
      const img = document.createElement('img');
      img.src = src;
      img.alt = label;
      fig.appendChild(img);
  
      const cap = document.createElement('figcaption');
      cap.textContent = label;
      fig.appendChild(cap);
  
      gallery.appendChild(fig);
    });
  
    /* ---------- light-box behaviour ---------- */
    gallery.addEventListener('click', e=>{
      if (e.target.tagName !== 'IMG') return;
      lightImg.src = e.target.src;
      lightImg.alt = e.target.alt;
      lightbox.classList.add('open');
    });
    // close with click on backdrop or ESC
    lightbox.addEventListener('click', ()=> lightbox.classList.remove('open'));
    document.addEventListener('keydown', e=>{
      if (e.key === 'Escape') lightbox.classList.remove('open');
    });
    return gallery;
  }

function reportProblem(feedbackInput, uselessCheckbox, file_name, is_problem, 
    run_index, is_checked = false, data_null = false, save_button = false, finalRow = null
) {
    const data = feedbackInput.value.trim();
    const useless = uselessCheckbox ? uselessCheckbox.checkbox.checked : false;
    fetch(`/${judge_id}/report_problem/`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            "description": data_null ? null : data,
            "file_name": file_name,
            "is_problem": is_problem,
            "run_index": run_index,
            "useless": useless,
            "is_checked": is_checked
        }),
    })
    .then((response) => {
        if (save_button) {
            updateStatus(response, finalRow.statusPill); // assumes `updateStatus` is defined globally
        }
      })
      .catch((error) => {
        if (save_button) {
            finalRow.statusPill.textContent = "Error saving grading!";
            finalRow.statusPill.classList.remove("bg-success", "bg-secondary");
            finalRow.statusPill.classList.add("bg-danger"); // red
        }
      })
      .finally(() => {
        if (save_button) {
            finalRow.saveBtn.disabled = false;
        }
      });
}

function createProblemFeedbackForm(id, label, is_problem = true, run_index = null, current_issue = null, 
    is_useless = false, add_useless = false
) {
    const form = document.createElement("form");
    form.className = "needs-validation d-flex flex-column gap-3";
    form.id = id;
    form.style.marginLeft = "1rem";
    form.style.marginRight = "1rem";
    
    const checkbox = addCheckbox(form, "checkbox-" + id, label, current_issue || is_useless);

    /* -------- Feedback textarea + Save button ------- */
    const feedbackGroup = document.createElement("div");
    feedbackGroup.className = "d-none flex-column gap-2"; // hidden until checked
    if (current_issue || is_useless) {
        feedbackGroup.classList.remove("d-none");
    }

    const feedbackLabel = document.createElement("label");
    feedbackLabel.className = "form-label fw-semibold";
    feedbackLabel.textContent = "Feedback";
    

    const feedbackInput = document.createElement("textarea");
    feedbackInput.className = "form-control";
    feedbackInput.rows = 3;
    if (!current_issue) {
        feedbackLabel.placeholder = "Describe problem...";
    } else {
        // set default to current issue
        feedbackInput.textContent = current_issue;
    }
    feedbackInput.style.marginBottom = "1rem";

    

    const finalRow = createSaveButton(id);

    feedbackGroup.append(feedbackLabel, feedbackInput);

    let uselessCheckbox = null;
    if (add_useless) {
        uselessCheckbox = addCheckbox(feedbackGroup, "useless-checkbox", 
            "The issue makes the problem ungradable (e.g., makes it trivial, nonsensical, ...)", is_useless);
    }
    feedbackGroup.append(finalRow.actionGroup);
    form.append(feedbackGroup)

    feedbackInput.onchange = () => {
        reportProblem(feedbackInput, uselessCheckbox, file_name, is_problem, run_index, false);
    }

    checkbox.checkbox.onchange = () => {
        if (checkbox.checkbox.checked) {
            feedbackGroup.classList.remove("d-none");
            feedbackInput.focus();
        } else {
            feedbackGroup.classList.add("d-none");
            feedbackInput.value = "";
            finalRow.statusPill.classList.add("d-none");
            reportProblem(feedbackInput, uselessCheckbox, file_name, is_problem, run_index, false, true);
        };
    }

    finalRow.saveBtn.onclick = () => {
        reportProblem(feedbackInput, uselessCheckbox, file_name, is_problem, run_index, true, false, true, 
            finalRow
        );
    };
    
    return form;
}

function getSelectedText() {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return null;

    const range = sel.getRangeAt(0);

    /* ────────────────────────────────────────────────
       1. Find the <div class="response-box"> that
          contains the *start* of the selection
    ──────────────────────────────────────────────────*/
    const responseBoxes = document.getElementsByClassName('response-box');
    let responseBox = null;
    for (let i = 0; i < responseBoxes.length; i++) {
      if (responseBoxes[i].contains(range.startContainer)) {
        responseBox = responseBoxes[i];
        break;
      }
    }
    // Bail out if the selection straddles boxes or not in a responseBox
    if (!responseBox || !responseBox.contains(range.endContainer)) return null;

    // Helper function to find the closest KaTeX ancestor
    const getKatexAncestor = (node, limitAncestor) => {
        let currentNode = node;
        while (currentNode && currentNode !== limitAncestor) {
            if (currentNode.nodeType === Node.ELEMENT_NODE &&
                (currentNode.classList.contains('katex') || currentNode.classList.contains('katex-display'))) {
                if (currentNode.querySelector('annotation[encoding="application/x-tex"]')) {
                    return currentNode;
                }
            }
            if (currentNode === limitAncestor) break; // Optimization: stop if we reach the overall container
            currentNode = currentNode.parentNode;
        }
        return null;
    };

    let selectedTextOutput = '';
    let n_equationsOutput = 0;

    const startKatexBlock = getKatexAncestor(range.startContainer, responseBox);
    const endKatexBlock = getKatexAncestor(range.endContainer, responseBox);

    if (startKatexBlock && startKatexBlock === endKatexBlock) {
        // Case 1: Selection is entirely within one KaTeX block
        const texNode = startKatexBlock.querySelector('annotation[encoding="application/x-tex"]');
        if (texNode) {
            selectedTextOutput = "$" + texNode.textContent + "$";
            n_equationsOutput = 1;
        } else {
            // Fallback if KaTeX block is malformed (should not happen)
            selectedTextOutput = range.toString();
        }
    } else {
        // Case 2: Mixed selection (text, multiple KaTeX blocks, or partial KaTeX with other text)
        // Use TreeWalker to iterate through nodes in the selection range within the responseBox
        const walker = document.createTreeWalker(
            responseBox, // Root for the walker
            NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, // Consider elements and text nodes
            {
                acceptNode: (node) => {
                    // Only accept nodes that are part of (intersect) the selection range
                    if (range.intersectsNode(node)) {
                        return NodeFilter.FILTER_ACCEPT;
                    }
                    return NodeFilter.FILTER_REJECT;
                }
            }
        );

        const processedOriginalKatexRoots = new Set(); // To avoid adding LaTeX from the same block multiple times

        let currentWalkNode;
        while (currentWalkNode = walker.nextNode()) {
            const katexRoot = getKatexAncestor(currentWalkNode, responseBox);

            if (katexRoot) {
                if (!processedOriginalKatexRoots.has(katexRoot)) {
                    // This is the first time we encounter a node from this KaTeX block.
                    // Add the entire KaTeX block's LaTeX.
                    const texNode = katexRoot.querySelector('annotation[encoding="application/x-tex"]');
                    if (texNode) {
                        selectedTextOutput += "$" + texNode.textContent + "$";
                        n_equationsOutput++;
                        processedOriginalKatexRoots.add(katexRoot);
                    }
                }
                // If currentWalkNode is part of a KaTeX block (katexRoot is not null),
                // we've already handled it by adding the full LaTeX for katexRoot.
                // So, we skip further processing of this node to avoid adding its visible text.
                continue;
            }

            // If we reach here, currentWalkNode is NOT part of a KaTeX block processed above.
            // It must be a text node or a non-KaTeX element whose text content should be extracted.
            if (currentWalkNode.nodeType === Node.TEXT_NODE) {
                let textContent = "";
                // Check if this text node is the start, end, or middle of the selection range
                if (range.startContainer === currentWalkNode && range.endContainer === currentWalkNode) {
                    textContent = currentWalkNode.textContent.substring(range.startOffset, range.endOffset);
                } else if (range.startContainer === currentWalkNode) {
                    textContent = currentWalkNode.textContent.substring(range.startOffset);
                } else if (range.endContainer === currentWalkNode) {
                    textContent = currentWalkNode.textContent.substring(0, range.endOffset);
                } else {
                    // Node is fully contained within the selection (and intersects, checked by walker)
                    // To be precise for fully contained nodes:
                    const nodeRange = document.createRange();
                    nodeRange.selectNodeContents(currentWalkNode);
                    if (range.compareBoundaryPoints(Range.START_TO_START, nodeRange) <= 0 &&
                        range.compareBoundaryPoints(Range.END_TO_END, nodeRange) >= 0) {
                        textContent = currentWalkNode.textContent;
                    }
                }
                selectedTextOutput += textContent;
            }
        }
    }

    /* ────────────────────────────────────────────────
       3. Count KaTeX blocks *before* the selection
    ──────────────────────────────────────────────────*/
    let firstSelectedNodeOrItsDirectChild = range.startContainer;
     // Adjust to be the element node itself if startContainer is a text node, for direct child comparison.
    if (firstSelectedNodeOrItsDirectChild.nodeType === Node.TEXT_NODE && firstSelectedNodeOrItsDirectChild.parentNode !== responseBox) {
        firstSelectedNodeOrItsDirectChild = firstSelectedNodeOrItsDirectChild.parentNode;
    }
    // Bubble up until it is a direct child of responseBox, or responseBox itself
    while (firstSelectedNodeOrItsDirectChild && firstSelectedNodeOrItsDirectChild.parentNode !== responseBox && firstSelectedNodeOrItsDirectChild !== responseBox) {
        firstSelectedNodeOrItsDirectChild = firstSelectedNodeOrItsDirectChild.parentNode;
    }
    // If the loop stopped because node is responseBox, or if startContainer was responseBox, there's no specific "first child" node.
    if (firstSelectedNodeOrItsDirectChild === responseBox) {
        firstSelectedNodeOrItsDirectChild = null; // Indicates selection might start at the beginning of responseBox or encompass it.
    }

    let katexBefore = 0;
    if (responseBox && responseBox.firstChild) {
        for (
            let node = responseBox.firstChild;
            node && (firstSelectedNodeOrItsDirectChild ? node !== firstSelectedNodeOrItsDirectChild : true); // Loop until the node before the selection's first relevant element
            node = node.nextSibling
        ) {
            if (node.nodeType !== Node.ELEMENT_NODE) continue;
            if (node.querySelector('[encoding="application/x-tex"]')) {
                katexBefore++;
            }
        }
    }
    return {
        selectedText: selectedTextOutput,
        n_equations: n_equationsOutput,
        n_equations_before: katexBefore,
    };
}

// NEW function
function createLlmJudgmentPanel(llmJudgment, attemptIndex) {
    const panelContainer = document.createElement("div");
    panelContainer.className = "llm-judgment-container marked box"; // Reuse existing styles + new
    panelContainer.style.flex = "0 0 30%"; // Match secondaryBox flex
    panelContainer.style.minHeight = "500px"; // Match secondaryBox minHeight
    panelContainer.style.whiteSpace = "pre-wrap";
    panelContainer.style.tabSize = "4";


    const tabDiv = document.createElement("div");
    tabDiv.className = "tab llm-judgment-tabs"; // Add specific class for LLM tabs

    const tabGroupIdentifier = `llm-judge-${attemptIndex}`;

    // Summary Tab Button
    const summaryButton = document.createElement("button");
    summaryButton.className = "tablinks";
    summaryButton.id = `tablinksummary-${tabGroupIdentifier}`;
    summaryButton.innerHTML = "LLM Summary";
    summaryButton.onclick = (event) => openTab(event, 'summary', tabGroupIdentifier);
    tabDiv.appendChild(summaryButton);

    // Issues Tab Button
    const issuesButton = document.createElement("button");
    issuesButton.className = "tablinks";
    issuesButton.id = `tablinkissues-${tabGroupIdentifier}`;
    issuesButton.innerHTML = `LLM Issues (${llmJudgment.issues ? llmJudgment.issues.length : 0})`;
    issuesButton.onclick = (event) => openTab(event, 'issues', tabGroupIdentifier);
    tabDiv.appendChild(issuesButton);

    panelContainer.appendChild(tabDiv);

    // Summary Tab Content
    const summaryContent = document.createElement("div");
    summaryContent.id = `tabsummary-${tabGroupIdentifier}`;
    summaryContent.className = "tabcontent llm-summary-content";
    summaryContent.style.display = "none"; // Hidden by default
    const summaryP = document.createElement("p");
    summaryP.textContent = llmJudgment.summary || "No summary provided.";
    summaryContent.appendChild(summaryP);
    panelContainer.appendChild(summaryContent);

    // Issues Tab Content
    const issuesContent = document.createElement("div");
    issuesContent.id = `tabissues-${tabGroupIdentifier}`;
    issuesContent.className = "tabcontent llm-issues-list";
    issuesContent.style.display = "none"; // Hidden by default

    if (llmJudgment.issues && llmJudgment.issues.length > 0) {
        llmJudgment.issues.forEach((issue, idx) => { // 'idx' will be our issue_index for FeedbackLLMJudge
            const issueBox = document.createElement("div");
            issueBox.className = "llm-issue-box";

            const issueLocation = document.createElement("p");
            issueLocation.innerHTML = `<strong>Location:</strong> ${issue.location || "N/A"}`;
            issueBox.appendChild(issueLocation);

            if (issue.text) {
                const issueTextP = document.createElement("p");
                if (issue.start_index !== null && issue.start_index !== undefined) {
                    const targetId = `llm-issue-target-${attemptIndex}-${issue.originalIssueIndex}`;
                    const InnerSpan = document.createElement("span");
                    InnerSpan.className = "llm-issue-cited-text clickable-cited-text";
                    InnerSpan.title = "Scroll to text in model solution";
                    InnerSpan.textContent = issue.text;
                    issueTextP.innerHTML = `<strong>Cited Text:</strong> ${InnerSpan.outerHTML}`;
                    const citedTextSpan = issueTextP.querySelector('.clickable-cited-text');
                    if (citedTextSpan) {
                        citedTextSpan.addEventListener('click', () => {
                            scrollToElementId(targetId, issue.text);
                        });
                    }
                } else {
                    const innerSpan = document.createElement("span");
                    innerSpan.className = "llm-issue-cited-text";
                    innerSpan.textContent = issue.text;
                    issueTextP.innerHTML = `<strong>Cited Text:</strong> ${innerSpan.outerHTML}`;
                }
                issueBox.appendChild(issueTextP);
            }

            const issueDescription = document.createElement("p");
            issueDescription.innerHTML = `<strong>Description:</strong> ${issue.description || "N/A"}`;
            issueBox.appendChild(issueDescription);

            const issueCategory = document.createElement("p");
            issueCategory.innerHTML = `<strong>Category:</strong> ${issue.category || "N/A"}`;
            issueBox.appendChild(issueCategory);

            // START: Add Accept/Reject buttons
            // const feedbackButtonContainer = document.createElement("div");
            // feedbackButtonContainer.className = "llm-feedback-button-container";

            // const acceptButton = document.createElement("button");
            // acceptButton.className = "llm-feedback-button accept-button";
            // acceptButton.textContent = "Accept";
            // // Call FeedbackLLMJudge with issue index (idx), attemptIndex, and true for accept
            
            // feedbackButtonContainer.appendChild(acceptButton);

            // const rejectButton = document.createElement("button");
            // rejectButton.className = "llm-feedback-button reject-button";
            // rejectButton.textContent = "Reject";
            // // Call FeedbackLLMJudge with issue index (idx), attemptIndex, and false for reject
            // rejectButton.onclick = () => {
            //     FeedbackLLMJudge(idx, attemptIndex, false);
            //     rejectButton.classList.add("selected");
            //     acceptButton.classList.remove("selected");
            // };

            // acceptButton.onclick = () => {
            //     FeedbackLLMJudge(idx, attemptIndex, true);
            //     acceptButton.classList.add("selected");
            //     rejectButton.classList.remove("selected");                      
            // };

            // // if issue.accepted is defined, set the button state
            // if (issue.accepted !== undefined) {
            //     if (issue.accepted) {
            //         acceptButton.classList.add("selected");
            //     } else {
            //         rejectButton.classList.add("selected");
            //     }
            // }

            // feedbackButtonContainer.appendChild(rejectButton);

            // issueBox.appendChild(feedbackButtonContainer);
            // END: Add Accept/Reject buttons

            issuesContent.appendChild(issueBox);
        });
    } else {
        const noIssuesP = document.createElement("p");
        noIssuesP.textContent = "No issues reported by LLM.";
        issuesContent.appendChild(noIssuesP);
    }
    panelContainer.appendChild(issuesContent);

    summaryContent.style.display = "block";
    issuesContent.style.display = "none";
    summaryButton.classList.add("active");
    if (issuesButton.classList.contains("active")) {
        issuesButton.classList.remove("active");
    }

    return panelContainer;
}

/**
 * Sends feedback for an LLM judgment issue to the backend.
 *
 * @async
 * @param {number} issueIndex - The index of the issue within the attempt's issue list.
 * @param {number} attemptIndex - The index of the attempt being judged.
 * @param {boolean} accept - True if the issue is accepted, false if rejected.
 *
 * Global variables expected to be defined elsewhere:
 * - judge_id: The identifier for the current judge or judging session.
 * - file_name: The name of the file associated with the attempt.
 */
async function FeedbackLLMJudge(issueIndex, attemptIndex, accept) {
    // Log the input for debugging (optional)
    const url = `/${judge_id}/llm_judge_feedback/`;

    const payload = {
        attemptIndex: attemptIndex,
        file_name: file_name,     // Global variable
        issueIndex: issueIndex,
        accepted: accept
    };

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // If your backend requires a CSRF token, you'll need to add it here.
                // For example, for Django:
                // 'X-CSRFToken': getCookie('csrftoken'), // Assuming you have a getCookie function
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const result = await response.json(); // Or response.text() if the server doesn't return JSON
        }
    } catch (error) {
    }
}


/**
 * Scrolls the view to the specified element ID.
 * @param {string} elementId - The ID of the element to scroll to.
 */
function scrollToElementId(elementId, issue_text) {
    const targetElement = document.getElementById(elementId);
    

    if (targetElement) {
        // targetElement.style.display = 'inline-block'; // Or any other appropriate display value
        targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // targetElement.style.display = 'none'; // Or any other appropriate display value

        // Optional: Temporary highlight for visual feedback.
        // Since the span is empty, highlighting it directly might not be very visible.
        // You could highlight its parent or give the span temporary visible style.
        targetElement.classList.add("highlight-orange");

        setTimeout(() => {
            if (targetElement) { // Check if element still exists
                targetElement.classList.remove("highlight-orange");
                // targetElement.style.display = 'none'; // Or any other appropriate display value
            }
        }, 2500);
    } else {
        console.warn(`[scrollToElementId] Element with ID not found: ${elementId}`);
    }
}