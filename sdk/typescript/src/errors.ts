/**
 * OmoiOS SDK errors.
 */

/** Base error class for OmoiOS SDK. */
export class OmoiOSError extends Error {
  /** HTTP status code if applicable */
  statusCode?: number;

  constructor(message: string, statusCode?: number) {
    super(message);
    this.name = 'OmoiOSError';
    this.statusCode = statusCode;
  }
}

/** Raised when authentication fails. */
export class AuthError extends OmoiOSError {
  constructor(message = 'Authentication failed') {
    super(message, 401);
    this.name = 'AuthError';
  }
}

/** Raised when a resource is not found. */
export class NotFoundError extends OmoiOSError {
  constructor(message = 'Resource not found') {
    super(message, 404);
    this.name = 'NotFoundError';
  }
}

/** Raised when request validation fails. */
export class ValidationError extends OmoiOSError {
  constructor(message = 'Validation failed') {
    super(message, 400);
    this.name = 'ValidationError';
  }
}

/** Raised when server returns 5xx error. */
export class ServerError extends OmoiOSError {
  constructor(message = 'Server error') {
    super(message, 500);
    this.name = 'ServerError';
  }
}
