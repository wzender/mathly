# Tasks

## 1. Server

- [x] 1.1 Make a class save without lessons (the stored list is every lesson of the bank, any `lessons` in a request is ignored) and give every student who is in a class every lesson (path, skills, collection, lessons list); verify API tests: a class created with no lessons works, a class stored with two lessons still gives its student the whole path, a student in no class sees none

## 2. Screens

- [x] 2.1 Take the lesson list out of the manager's class form and class cards, and name the subject card "מתמטיקה כיתה ט - מצוינות"; verify browser tests: the form has no lesson checkboxes and a class saves, the card shows the course name

## 3. Wrap-up

- [x] 3.1 Update the PRD (classes, subject card), run the full suite and `openspec validate one-course-for-all-classes --strict`; verify both pass
