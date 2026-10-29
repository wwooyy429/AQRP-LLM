function compareReturnedSources(local, native, projectId) {
  const clean = value => value.replace(/^\uFEFF/, "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (native.success !== true || native.errors?.length || native.project?.projectId !== projectId ||
      native.project.language !== "Py" || !Array.isArray(native.project.files)) throw Error("Invalid project source response");
  const observed = new Map(), aliases = new Set();
  let ignored = 0, generated = 0;
  for (const file of native.project.files) {
    if (typeof file.filePath !== "string" || typeof file.content !== "string" ||
        aliases.has(file.filePath.toLowerCase())) throw Error("Invalid or duplicate source path");
    aliases.add(file.filePath.toLowerCase());
    if (!file.filePath.toLowerCase().endsWith(".py")) { ignored++; continue; }
    if (["_engineering_task_input.py","_collection_task_input.py"].includes(file.filePath)) { generated++; continue; }
    observed.set(file.filePath, file.content);
  }
  const expected = new Map(local.map(file => [file.path, file]));
  const names = [...new Set([...expected.keys(), ...observed.keys()])].sort();
  const files = names.map(path => ({
    path, expected_sha256: expected.get(path)?.sha256 ?? null,
    observed_normalized_source_equals_expected: expected.has(path) && observed.has(path) &&
      clean(observed.get(path)) === expected.get(path).content,
    expected_characters: expected.get(path)?.content.length ?? null,
    observed_characters: observed.get(path)?.length ?? null
  }));
  return {schema_version:1, kind:"exact_returned_Python_source_comparison",
    project_id:projectId, expected_implementation_count:expected.size,
    observed_implementation_count:observed.size, ignored_non_python_count:ignored,
    ignored_generated_input_count:generated, files,
    source_reference_matches:files.length === expected.size && files.every(file => file.observed_normalized_source_equals_expected),
    normalization:"UTF-8-sig universal newlines; preserve all terminal LF characters",
    comparison:"actual returned managed Python source strings compared to frozen local source strings",
    full_native_response_not_exported:true, notebook_contents_not_exported:true,
    worker_source_verified:false, full_cloud_inventory_certified:false,
    financial_evidence:false, budget_admission_performed:false, ready_to_dispatch:false};
}
