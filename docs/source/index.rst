Async Jobs Library Documentation
==================================

.. image:: https://img.shields.io/badge/python-3.11+-blue.svg
   :alt: Python Version

A reusable async job platform library for FastAPI projects with PostgreSQL job store,
SQS transport, and ECS-friendly scheduler/worker processes.

Features
--------

- **FastAPI Integration**: Drop-in router for job enqueueing endpoints
- **PostgreSQL Job Store**: Reliable job persistence with deadline-based scheduling
- **SQS Transport**: AWS SQS for job message queuing
- **Multi-tenant**: Built-in tenant isolation and quota enforcement
- **Deadline-based Scheduling**: Meta-style delay tolerance for flexible job execution
- **ECS Ready**: Environment-based configuration and graceful shutdown
- **Retry Logic**: Configurable backoff strategies (exponential, linear, constant)
- **Job Registry**: Decorator-based handler registration

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   quickstart
   user_guide
   api_reference
   deployment
   development

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
