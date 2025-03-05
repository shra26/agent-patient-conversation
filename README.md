Usage details:
Please send an email to me before making the call so I can turn on the server(default off as I haven't confgured my vpc and security groups on AWS correctly). 
The phone number to call is 
**+12184837553**

Assumptions:
1. The storage of conversation should Ideally be saved into a NoSQL db like DynamoDB(Not implemented on this solution but will be easy to add if needed)
2. I have tried basic processing of information with Regex, I understand this in not ideal as there is a chance to miss the information provided by the caller, will need to integrate further NLP to avoid this issue. Email sender sometime does not work due to this issue, I'm sure if we were to collaborate we could find a solution for this.


Extra Notes:
To create the SIP inbound trunk and dispatch rules 
```python
lk sip inbound create inbound-trunk.json
lk sip dispatch create dispatch-rule.json

```