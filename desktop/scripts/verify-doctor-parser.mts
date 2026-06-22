import { parseDoctorJson } from "../src/lib/status.ts";

const input = '{"ok":true,"can_split":true,"can_translate":true,"checks":[]}';
const result = parseDoctorJson(input);
console.log(JSON.stringify(result));

if (
  result.ok !== true ||
  result.canSplit !== true ||
  result.canTranslate !== true ||
  !Array.isArray(result.checks)
) {
  console.error("parseDoctorJson fixture FAILED");
  process.exit(1);
}

console.log("parseDoctorJson fixture PASS");
