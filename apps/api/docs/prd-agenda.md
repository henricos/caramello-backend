# PRD – Family Calendar

## 1. Purpose of the Document

This document describes the functional requirements of **Caramello's Family Calendar**, defining behaviors, flows, rules and responsibilities related to the use of family appointments and events. It complements the Project Vision and the Core PRD.

This PRD does not address technical decisions, data modeling or integration details at the API level.

---

## 2. Scope of the PRD (MVP)

### 2.1 Included Functionality

* Shared family calendar
* Creation, editing and removal of appointments
* Visualization by family and by member
* Conceptual integration with an external calendar
* Basic event synchronization

### 2.2 Out of Scope

* Personal calendars independent of the family
* Professional calendars
* Advanced recurrence rules
* External sharing outside the family

---

## 3. Fundamental Concepts

### Family Calendar

Calendar shared among all members of the family, used as the central reference for collective appointments.

### Appointment

Event with a defined date and time, which may represent family appointments or individual ones visible in the family's context.

### Responsible Member

Family member associated with an appointment, indicating who is directly involved.

### Source of Truth

The external calendar linked by the family owner is considered the primary source of appointment data.

---

## 4. Principles of the Family Calendar

* There is **a single calendar per family**
* The calendar conceptually belongs to the family, not to an individual
* All members see the calendar's appointments
* Appointments may be associated with one or more members
* Caramello acts as the interface for creation, visualization and organization

---

## 5. Roles and Permissions

### Owner

* Link the family's external calendar
* Create, edit and remove appointments
* View all appointments

### Member

* Create appointments
* Edit or remove appointments they created
* View all appointments

---

## 6. Creation of Appointments

### 6.1 Functional Data of an Appointment

* Title
* Date and time
* Location (optional)
* Description (optional)
* Members involved

### 6.2 Behavior

* Any member can create an appointment
* Created appointments become part of the family calendar
* Appointments may involve the whole family or specific members

---

## 7. Editing and Removal of Appointments

### 7.1 Editing

* The creator of the appointment can edit it
* The owner can edit any appointment

### 7.2 Removal

* The creator can remove the appointment
* The owner can remove any appointment

---

## 8. Calendar Visualization

### 8.1 Visualization Modes

* Overall family view
* View filtered by member

### 8.2 Representation

* Appointments are presented chronologically
* Past events remain accessible for consultation

---

## 9. Integration with an External Calendar (Functional View)

* The external calendar is linked by the family owner
* Caramello reflects the events of the external calendar
* Appointments created in Caramello must appear in the external calendar

---

## 10. Synchronization and Consistency

* Changes made in Caramello must be reflected in the external calendar
* Changes made directly in the external calendar must be reflected in Caramello
* In case of conflict, the last known change prevails

---

## 11. States and Exceptional Situations

* Calendar not linked: functionality unavailable
* Synchronization failure: the user is informed
* Removal of the external integration: the calendar becomes inaccessible

---

## 12. User Experience (Functional View)

### Calendar Onboarding

* The owner links the family's calendar

### Daily Use

* Quick view of upcoming appointments
* Simplified event creation

---

## 13. Out of Scope and Future Evolutions

* Advanced recurrence rules
* Smart notifications
* Integration with multiple external calendars
* Automation of appointments by a virtual assistant

---

## 14. Acceptance Criteria

* All members see the same calendar
* Created appointments are synchronized
* Permissions are respected
* Failures are communicated clearly

---

## 15. Final Considerations

This PRD defines the functional behavior of Caramello's Family Calendar. Technical and integration details are described in specific documents.
