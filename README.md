You can start the server with command docker-compose build && docker-compose up.

After that, visit the home page at http://127.0.0.1:8000/ which will bring you to the weekly_schedule if you have an account. Otherwise, you will have to create an account by providing a Canvas access token. After logging in you will be prompted to enter PIN number which you can obtain from Coursys by following a link that will be given.

For details about Canvas tokens, visit https://canvas.instructure.com/doc/api/file.oauth.html#manual-token-generation

Coursys authentication is accomplished through the OAuth1.0a protocol using rauth library on our side. Sometimes it can get a little stubborn, but after a little time or a few retries, it always works.

The project also features it's own API. To access it, a registered user needs to obtain a token, which can be done in their profile page or by sending a POST request at /api/obtain-token/ endpoint with the student_id as 'username' and password as 'password'. There are only two endpoints available: /api/all-courses/ lists all courses in the current semester, and /api/assignments/&lt;course_id&gt;/ provides information about grades and assignments. Each request should include HTTP Authorization header in the following format: 'Authorization: Token &lt;your token&gt;'.