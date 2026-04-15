from class_script import build_and_serialize
from loadInputDataToJson import process_input_data
from UI_form import run_editor

input_folder_name = "./UC_InputData_Public"

# Output filename (without extension, same name for json and ttl)
output_filename = "Nibelungen_Spaces_Public"

json_data_path = process_input_data(input_folder_name, output_filename=output_filename)

editor_status = run_editor(json_data_path)
print("Editor ended with status:", editor_status)  # "finished" or "closed"
rdf_graph_path = build_and_serialize(json_data_path, output_filename=output_filename)
print("Saved data to ttl file: ", rdf_graph_path)
