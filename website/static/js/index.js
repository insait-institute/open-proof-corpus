var sidebar_info = [];
var raw_file_data = null;
var file_name = null;
var judge_id = null;
// get window href, find judge id
function getJudgeId() {
    // last part of the url
    const url_path = window.location.pathname;
    const url_path_array = url_path.split("/");
    const judge_id = url_path_array[url_path_array.length - 1];
    if (judge_id && judge_id.length !== 0) {
        return judge_id;
    } else {
        return url_path_array[url_path_array.length - 2];
    }
}

judge_id = getJudgeId();
const is_super = judge_id.startsWith("super-")
// get href judge id
async function fetchData() {
  try {
      // 1. Fetch sidebar_info first
      const response = await fetch(`/${judge_id}/file_names/`);
      sidebar_info = await response.json(); // Assuming sidebar_info is a global/outer scope variable

      const url_search = window.location.search;
      let current_file_name_from_url = new URLSearchParams(url_search).get("file_name");

      // 2. Check if file_name is missing from the URL
      if (!current_file_name_from_url) {
          let first_filename_to_set = null;

          // 3. Determine the first_filename_to_set
          // Option A: Simplest - use the very first file from the raw list
          if (sidebar_info && sidebar_info.file_names && sidebar_info.file_names.length > 0) {
              first_filename_to_set = sidebar_info.file_names[0];
          }

          if (first_filename_to_set) {
              // 4. Redirect immediately if a default file is found
              const url = new URL(window.location.href);
              url.searchParams.set("file_name", first_filename_to_set);
              window.location.href = url.href;
              return; // IMPORTANT: Stop further execution on this initial load
          }
          // If no first_filename_to_set (e.g., no files at all), it will fall through.
      }

      // 5. If file_name was present, or after a redirect, proceed.
      addFileNamesToSidebar(sidebar_info, current_file_name_from_url);

      // Update the global file_name variable
      file_name = current_file_name_from_url;

      if (file_name && file_name.length !== 0) {
          const data_response = await fetch(`/${judge_id}/data/` + file_name + "/");
          raw_file_data = await data_response.json(); // Assuming raw_file_data is global/outer scope
          renderTraceContent(raw_file_data);
      } else {
          // Handle case where no file is selected or available after all checks
          // (e.g., clear main content or show a "No files available" message in main area)
          console.log("No file name to load content for.");
          // Example: document.getElementById('main-content-display-area').innerHTML = 'Please select a file.';
      }

  } catch (error) {
      console.error('Error fetching results:', error);
      // Consider showing an error message in the UI
      // Example: document.getElementById('main-content-display-area').innerHTML = 'Error loading data.';
  }
}

fetchData();