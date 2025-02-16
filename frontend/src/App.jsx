import { useState, useEffect } from 'react';
import { Container, Button, Card, Form, Row, Col } from 'react-bootstrap';
import 'bootstrap/dist/css/bootstrap.min.css'
export default function App() {
  const [courses, setCourses] = useState([]);
  const [expandedCourse, setExpandedCourse] = useState(null);
  const [file, setFile] = useState(null);

  useEffect(() => {
    fetchCourses();
  }, []);

  const fetchCourses = async () => {
    try {
      const response = await fetch('http://localhost:8000/courses/');
      const data = await response.json();
      setCourses(data);
    } catch (error) {
      console.error('Error fetching courses:', error);
    }
  };

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      await fetch('http://localhost:8000/upload/', {
        method: 'POST',
        body: formData,
      });
      fetchCourses();
    } catch (error) {
      console.error('Error uploading file:', error);
    }
  };

  const handleCourseClick = async (courseCode) => {
    if (expandedCourse?.course_code === courseCode) {
      setExpandedCourse(null); // Collapse if already expanded
      return;
    }
    try {
      const response = await fetch(`http://localhost:8000/course/${courseCode}`);
      const data = await response.json();
      setExpandedCourse({ course_code: courseCode, syllabus: data });
    } catch (error) {
      console.error('Error fetching course details:', error);
    }
  };

  return (
    <Container className="p-4">
      <h1 className="text-center">Syllabus Upload & View</h1>
      <Form.Group controlId="formFile" className="mt-3">
        <Form.Control type="file" accept=".pdf" onChange={handleFileChange} />
      </Form.Group>
      <Button className="mt-2" variant="primary" onClick={handleUpload}>Upload</Button>
      <h2 className="mt-4">Uploaded Courses</h2>
      <Row className="mt-2">
        {courses.map((course) => (
          <Col key={course.course_code} md={4} className="mb-3">
            <Card className="cursor-pointer" onClick={() => handleCourseClick(course.course_code)}>
              <Card.Body>
                <Card.Title>{course.course_code}</Card.Title>
                <Card.Text>{course.title}</Card.Text>
              </Card.Body>
              {expandedCourse?.course_code === course.course_code && (
                <Card.Footer className="bg-light">
                  <pre className="p-2 bg-white border rounded">
                    {JSON.stringify(expandedCourse.syllabus, null, 2)}
                  </pre>
                </Card.Footer>
              )}
            </Card>
          </Col>
        ))}
      </Row>
    </Container>
  );
}
