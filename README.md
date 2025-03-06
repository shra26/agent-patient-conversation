agent-v2.py is the latest version of the Ai Agent

Usage details:
Please send an email to me before making the call so I can turn on the AWS EC2 server(it's default off as I haven't configured my vpc and security groups on AWS correctly). 
The phone number to call is 
**+12184837553**

Assumptions:
1. The storage of conversation should ideally be saved into a NoSQL db like DynamoDB(Not implemented on this solution but will be easy to add if needed. 
The schedule table might work out better if added to a SQL db.
2. I have tried basic processing of information with Regex. I understand this is not ideal as there is a chance of missing the information provided by the caller, so we will need to integrate further NLP to avoid this issue. Email sending sometimes does not work due to this issue. We could find a solution if we were to collaborate.


Extra Notes:
To create the SIP inbound trunk and dispatch rules 
```python
lk sip inbound create inbound-trunk.json
lk sip dispatch create dispatch-rule.json

```
