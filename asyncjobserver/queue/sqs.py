"""AWS SQS queue implementation for job distribution."""

import json
from typing import Dict, Any, Optional, List

import boto3
from botocore.exceptions import ClientError

from asyncjobserver.job import JobPriority


class SQSQueue:
    """
    AWS SQS-based queue for distributing jobs to workers.
    
    This class provides integration with Amazon SQS for reliable job
    distribution across multiple workers. It supports multiple priority
    queues and handles message serialization/deserialization.
    
    Example:
        ```python
        queue = SQSQueue(
            region_name="us-east-1",
            queue_name_prefix="asyncjobs"
        )
        
        # Send a job to the queue
        await queue.send_job(job_data, priority=JobPriority.HIGH)
        
        # Receive jobs from the queue
        messages = await queue.receive_jobs(priority=JobPriority.HIGH, max_messages=10)
        ```
    """

    def __init__(
        self,
        region_name: str = "us-east-1",
        queue_name_prefix: str = "asyncjobs",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        """
        Initialize SQS queue client.
        
        Args:
            region_name: AWS region name
            queue_name_prefix: Prefix for queue names
            aws_access_key_id: AWS access key (uses default credentials if not provided)
            aws_secret_access_key: AWS secret key (uses default credentials if not provided)
            endpoint_url: Optional endpoint URL for local testing (e.g., LocalStack)
        """
        self.region_name = region_name
        self.queue_name_prefix = queue_name_prefix
        
        client_kwargs = {
            "region_name": region_name,
        }
        
        if aws_access_key_id and aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = aws_access_key_id
            client_kwargs["aws_secret_access_key"] = aws_secret_access_key
            
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        
        self.sqs = boto3.client("sqs", **client_kwargs)
        self.queue_urls: Dict[JobPriority, str] = {}

    def _get_queue_name(self, priority: JobPriority) -> str:
        """Get the queue name for a given priority."""
        return f"{self.queue_name_prefix}-{priority.value}"

    async def initialize(self) -> None:
        """
        Create SQS queues for each priority level if they don't exist.
        
        This method is not truly async but follows the pattern for consistency
        with other storage/queue implementations.
        """
        for priority in JobPriority:
            queue_name = self._get_queue_name(priority)
            
            try:
                response = self.sqs.create_queue(
                    QueueName=queue_name,
                    Attributes={
                        "MessageRetentionPeriod": "86400",  # 1 day
                        "VisibilityTimeout": "300",  # 5 minutes
                    },
                )
                self.queue_urls[priority] = response["QueueUrl"]
            except ClientError as e:
                if e.response["Error"]["Code"] == "QueueAlreadyExists":
                    response = self.sqs.get_queue_url(QueueName=queue_name)
                    self.queue_urls[priority] = response["QueueUrl"]
                else:
                    raise

    def send_job(
        self,
        job_data: Dict[str, Any],
        priority: JobPriority = JobPriority.MEDIUM,
        delay_seconds: int = 0,
    ) -> str:
        """
        Send a job to the appropriate priority queue.
        
        Args:
            job_data: Job data dictionary
            priority: Job priority level
            delay_seconds: Optional delay before the message becomes visible
            
        Returns:
            Message ID from SQS
        """
        if priority not in self.queue_urls:
            raise ValueError(f"Queue for priority {priority} not initialized")

        queue_url = self.queue_urls[priority]
        
        message_body = json.dumps(job_data)
        
        response = self.sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body,
            DelaySeconds=min(delay_seconds, 900),  # SQS max is 900 seconds
        )
        
        return response["MessageId"]

    def receive_jobs(
        self,
        priority: JobPriority = JobPriority.MEDIUM,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Receive jobs from the queue.
        
        Args:
            priority: Priority queue to receive from
            max_messages: Maximum number of messages to receive (1-10)
            wait_time_seconds: Long polling wait time (0-20 seconds)
            
        Returns:
            List of message dictionaries containing job data and receipt handles
        """
        if priority not in self.queue_urls:
            raise ValueError(f"Queue for priority {priority} not initialized")

        queue_url = self.queue_urls[priority]
        
        response = self.sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=min(max_messages, 10),
            WaitTimeSeconds=min(wait_time_seconds, 20),
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )
        
        messages = []
        for message in response.get("Messages", []):
            try:
                job_data = json.loads(message["Body"])
                messages.append(
                    {
                        "job_data": job_data,
                        "receipt_handle": message["ReceiptHandle"],
                        "message_id": message["MessageId"],
                    }
                )
            except json.JSONDecodeError:
                # Skip malformed messages
                continue
                
        return messages

    def delete_message(self, receipt_handle: str, priority: JobPriority) -> None:
        """
        Delete a message from the queue after successful processing.
        
        Args:
            receipt_handle: Receipt handle from receive_jobs
            priority: Priority queue the message came from
        """
        if priority not in self.queue_urls:
            raise ValueError(f"Queue for priority {priority} not initialized")

        queue_url = self.queue_urls[priority]
        
        self.sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
        )

    def change_message_visibility(
        self,
        receipt_handle: str,
        priority: JobPriority,
        visibility_timeout: int,
    ) -> None:
        """
        Change the visibility timeout of a message.
        
        Useful for extending processing time for long-running jobs.
        
        Args:
            receipt_handle: Receipt handle from receive_jobs
            priority: Priority queue the message came from
            visibility_timeout: New visibility timeout in seconds (0-43200)
        """
        if priority not in self.queue_urls:
            raise ValueError(f"Queue for priority {priority} not initialized")

        queue_url = self.queue_urls[priority]
        
        self.sqs.change_message_visibility(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=min(visibility_timeout, 43200),
        )

    def get_queue_attributes(self, priority: JobPriority) -> Dict[str, Any]:
        """
        Get attributes of a priority queue.
        
        Args:
            priority: Priority queue to query
            
        Returns:
            Dictionary of queue attributes
        """
        if priority not in self.queue_urls:
            raise ValueError(f"Queue for priority {priority} not initialized")

        queue_url = self.queue_urls[priority]
        
        response = self.sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=["All"],
        )
        
        return response.get("Attributes", {})

    def purge_queue(self, priority: JobPriority) -> None:
        """
        Delete all messages from a queue.
        
        Args:
            priority: Priority queue to purge
        """
        if priority not in self.queue_urls:
            raise ValueError(f"Queue for priority {priority} not initialized")

        queue_url = self.queue_urls[priority]
        
        self.sqs.purge_queue(QueueUrl=queue_url)
