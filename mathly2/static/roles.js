// The five roles: their Hebrew names and what each allows (shown on the "my access" page).
export const ROLE_ORDER = ["student", "teacher", "manager", "admin", "developer"];
export const ROLE_NAMES = { student: "תלמיד", teacher: "מורה", manager: "מנהל כיתות", admin: "מנהל הרשאות", developer: "מפתח" };
export const ROLE_ALLOWS = {
  student: "לתרגל במסלול, ולראות את ההתקדמות, הציונים והמשימות שלי.",
  teacher: "לראות את הכיתות שאני מלמד/ת ואת התלמידים בהן, ולהוסיף ולהסיר תלמידים בכיתות שלי.",
  manager: "ליצור, לערוך ולמחוק כיתות (שיעורים, מורה ותלמידים), ולראות את כל התלמידים. בלי גישה לנתוני למידה.",
  admin: "לתת תפקידים לחשבונות ולהסיר אותם. בלי גישה לנתוני למידה.",
  developer: "כל ההרשאות, לכל הכיתות והחשבונות, וכלי המפתח.",
};
/** The roles whose screens a person can open: their own, and for a developer all of them. */
export const visibleRoles = roles => roles.includes("developer") ? ROLE_ORDER : ROLE_ORDER.filter(role => roles.includes(role));
